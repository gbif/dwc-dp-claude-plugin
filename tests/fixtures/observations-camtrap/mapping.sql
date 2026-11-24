-- Camera traps from a Camtrap DP 1.0 package: the Camtrap DP example (MICA, INBO).
-- Load first: deployments.csv, media.csv, observations.csv as src_deployments, src_media,
-- src_observations. datapackage.json is read where it is. See references/recipes/observations.md.
--
-- Agreed with the data holder:
--   * the event-level observations of animals become occurrences. The media-level observations
--     classify the same animals image by image, so publishing both would count them twice; blank,
--     unknown, unclassified, vehicle and human observations report no organism;
--   * images showing people stay out for privacy (they are the ones with filePublic false), as do
--     images of sequences that aren't published;
--   * the images carry the package's media licence, CC BY 4.0.
-- Chosen for this example, as the recipe proposes:
--   * one event per deployment (eventType Sensor), and one per published sequence under it;
--   * each camera is an agent (agentType 'camera', a schema example) that recorded its deployment;
--     who set it up is an agent too, when named;
--   * camera set-up without a field as assertions about the deployment;
--   * the name as an identification based on the occurrence, with the taxon's ID and rank from the
--     package's taxonomic list; the classification method and probability as assertions.

DELETE FROM event_media;
DELETE FROM media;
DELETE FROM occurrence_assertion;
DELETE FROM identification;
DELETE FROM occurrence;
DELETE FROM event_assertion;
DELETE FROM event_agent_role;
DELETE FROM agent;
DELETE FROM event;

CREATE OR REPLACE TEMP TABLE published AS
SELECT * FROM src_observations WHERE observationLevel = 'event' AND observationType = 'animal';

CREATE OR REPLACE TEMP TABLE taxa AS
SELECT t.scientificName, t.taxonID, t.taxonRank, t.vernacularNames.eng AS vernacularName
FROM (SELECT unnest(taxonomic) AS t FROM read_json('datapackage.json'));

-- 1. Deployments: where each camera stood, from when to when. Camtrap DP gives coordinates in
--    WGS84, and coordinateUncertainty in metres.
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, locationID, locality, habitat,
                   decimalLatitude, decimalLongitude, geodeticDatum, coordinateUncertaintyInMeters, eventRemarks)
SELECT deploymentID, deploymentID, 'context', 'Sensor', deploymentStart || '/' || deploymentEnd,
       locationID, locationName, habitat, CAST(latitude AS DOUBLE), CAST(longitude AS DOUBLE),
       'EPSG:4326', CAST(coordinateUncertainty AS DOUBLE), nullif(deploymentComments, '')
FROM src_deployments;

-- The cameras, and the people who set them up (one is anonymized in the data, and kept as written).
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT DISTINCT 'camera:' || cameraID, 'camera', concat_ws(' ', cameraModel, 'camera', cameraID) FROM src_deployments
UNION ALL
SELECT DISTINCT 'person:' || setupBy, 'person', setupBy FROM src_deployments WHERE nullif(setupBy, '') IS NOT NULL;

INSERT INTO event_agent_role (event_fk, agent_fk, agentRole, agentRoleOrder)
SELECT deploymentID, 'camera:' || cameraID, 'recorded by', 1 FROM src_deployments
UNION ALL
SELECT deploymentID, 'person:' || setupBy, 'setupBy', 1 FROM src_deployments WHERE nullif(setupBy, '') IS NOT NULL;

-- How each camera was set up: Camtrap DP deployment fields without a DwC-DP field, with their units.
INSERT INTO event_assertion (assertionID, event_fk, verbatimAssertionType, assertionType, assertionValue, assertionUnit)
SELECT deploymentID || ':' || a.verbatim, deploymentID, a.verbatim, a.type, a.value, a.unit
FROM src_deployments,
     LATERAL (VALUES ('cameraDelay', 'camera delay', cameraDelay, 's'),
                     ('cameraHeight', 'camera height', cameraHeight, 'm'),
                     ('cameraDepth', 'camera depth', cameraDepth, 'm'),
                     ('cameraTilt', 'camera tilt', cameraTilt, 'degrees'),
                     ('cameraHeading', 'camera heading', cameraHeading, 'degrees'),
                     ('detectionDistance', 'detection distance', detectionDistance, 'm'),
                     ('baitUse', 'bait use', baitUse, NULL),
                     ('featureType', 'feature type', featureType, NULL),
                     ('deploymentGroups', 'deployment groups', deploymentGroups, NULL),
                     ('deploymentTags', 'deployment tags', deploymentTags, NULL)) AS a(verbatim, type, value, unit)
WHERE nullif(a.value, '') IS NOT NULL;

-- 2. Sequences: one event per published sequence, under its deployment, first to last image.
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventDate)
SELECT DISTINCT eventID, eventID, deploymentID, 'occurrence',
       CASE WHEN eventStart = eventEnd THEN eventStart ELSE eventStart || '/' || eventEnd END
FROM published;

-- 3. Observations: an occurrence each, its name as an identification, and how it was classified.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus,
                        organismQuantity, organismQuantityType, lifeStage, sex, behavior, occurrenceRemarks)
SELECT observationID, observationID, eventID, 'detected', count, 'individuals',
       nullif(lifeStage, ''), nullif(sex, ''), nullif(behavior, ''), nullif(observationComments, '')
FROM published;

INSERT INTO identification (identification_pk, identificationID, occurrence_fk, isAcceptedIdentification,
                            scientificName, taxonID, taxonRank, vernacularName, identifiedBy, dateIdentified)
SELECT p.observationID || ':id', p.observationID || ':id', p.observationID, true, p.scientificName,
       t.taxonID, t.taxonRank, t.vernacularName, p.classifiedBy, p.classificationTimestamp
FROM published p LEFT JOIN taxa t USING (scientificName);

INSERT INTO occurrence_assertion (assertionID, occurrence_fk, verbatimAssertionType, assertionType, assertionValue)
SELECT observationID || ':' || a.verbatim, observationID, a.verbatim, a.type, a.value
FROM published,
     LATERAL (VALUES ('classificationMethod', 'classification method', classificationMethod),
                     ('classificationProbability', 'classification probability', classificationProbability)) AS a(verbatim, type, value)
WHERE nullif(a.value, '') IS NOT NULL;

-- 4. Images: the public images of the published sequences. The media-level observations say which
--    sequence each image belongs to.
CREATE OR REPLACE TEMP TABLE sequence_media AS
SELECT DISTINCT o.mediaID, o.eventID
FROM src_observations o
WHERE o.observationLevel = 'media' AND o.eventID IN (SELECT eventID FROM published);

INSERT INTO media (media_pk, mediaID, mediaType, accessURI, format, createDate, license)
SELECT m.mediaID, m.mediaID, 'StillImage', m.filePath, m.fileMediatype, m.timestamp,
       'http://creativecommons.org/licenses/by/4.0/'
FROM src_media m
WHERE m.filePublic = 'true' AND m.mediaID IN (SELECT mediaID FROM sequence_media);

INSERT INTO event_media (media_fk, event_fk)
SELECT s.mediaID, s.eventID FROM sequence_media s JOIN media m ON m.media_pk = s.mediaID;
