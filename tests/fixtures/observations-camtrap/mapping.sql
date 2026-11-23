-- Camera traps (made up), from the three tables of a Camtrap DP package.
-- Load first: deployments.csv, media.csv, observations.csv as src_deployments, src_media,
-- src_observations. The choices marked "agreed" are the data holder's; see
-- references/recipes/observations.md.

DELETE FROM event_media;
DELETE FROM media;
DELETE FROM occurrence_assertion;
DELETE FROM occurrence;
DELETE FROM event_assertion;
DELETE FROM event_agent_role;
DELETE FROM agent;
DELETE FROM event;

-- Agreed: only sequences with animals are published. Blank sequences have nothing to report, and
-- sequences of people stay out to protect their privacy, with their images.
CREATE OR REPLACE TEMP TABLE published AS
SELECT * FROM src_observations WHERE observationLevel = 'event' AND observationType = 'animal';

-- One event per deployment: where the camera stood and from when to when. Camtrap DP gives the
-- coordinates in WGS84, hence EPSG:4326. Agreed: eventCategory 'context' and eventType 'Sensor'
-- (GBIF's eventType concept, whose labels include "Deployment").
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, locationID, locality, habitat,
                   decimalLatitude, decimalLongitude, geodeticDatum, coordinateUncertaintyInMeters)
SELECT deploymentID, deploymentID, 'context', 'Sensor', deploymentStart || '/' || deploymentEnd,
       locationID, locationName, habitat, CAST(latitude AS DOUBLE), CAST(longitude AS DOUBLE),
       'EPSG:4326', CAST(coordinateUncertainty AS DOUBLE)
FROM src_deployments;

-- The camera set-up, as assertions about the deployment.
INSERT INTO event_assertion (assertionID, event_fk, assertionType, assertionValue, assertionUnit)
SELECT deploymentID || ':' || t, deploymentID, t, v, u
FROM src_deployments,
     LATERAL (VALUES ('cameraModel', cameraModel, NULL), ('cameraHeight', cameraHeight, 'm'), ('baitUse', baitUse, NULL)) AS a(t, v, u)
WHERE v IS NOT NULL;

-- Who set up each camera. Agreed: the role keeps Camtrap DP's name for it, setupBy.
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT DISTINCT lower(replace(setupBy, ' ', '-')), 'person', setupBy FROM src_deployments;

INSERT INTO event_agent_role (event_fk, agent_fk, agentRole, agentRoleOrder)
SELECT deploymentID, lower(replace(setupBy, ' ', '-')), 'setupBy', 1 FROM src_deployments;

-- One event per published sequence, within its deployment, from its first to its last image.
-- Agreed: eventCategory 'occurrence'.
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventDate)
SELECT DISTINCT eventID, eventID, deploymentID, 'occurrence',
       CASE WHEN eventStart = eventEnd THEN eventStart ELSE eventStart || '/' || eventEnd END
FROM published;

-- One occurrence per observation, with who or what classified it.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, scientificName,
                        organismQuantity, organismQuantityType, lifeStage, sex, behavior,
                        identifiedBy, dateIdentified)
SELECT observationID, observationID, eventID, 'detected', scientificName,
       count, 'individuals', nullif(lifeStage, ''), nullif(sex, ''), nullif(behavior, ''),
       classifiedBy, classificationTimestamp
FROM published;

-- How it was classified, as assertions about the occurrence (agreed).
INSERT INTO occurrence_assertion (assertionID, occurrence_fk, assertionType, assertionValue)
SELECT observationID || ':' || t, observationID, t, v
FROM published,
     LATERAL (VALUES ('classificationMethod', classificationMethod), ('classificationProbability', classificationProbability)) AS a(t, v)
WHERE v IS NOT NULL;

-- The public images of the published sequences. Agreed: an image belongs to a sequence when it was
-- taken by the same deployment between the sequence's start and end, compared as times (not as text,
-- so that different time zone offsets compare correctly).
INSERT INTO media (media_pk, mediaID, mediaType, accessURI, format, createDate)
SELECT DISTINCT m.mediaID, m.mediaID, 'StillImage', m.filePath, m.fileMediatype, m.timestamp
FROM src_media m JOIN published p ON p.deploymentID = m.deploymentID
     AND CAST(m.timestamp AS TIMESTAMPTZ) BETWEEN CAST(p.eventStart AS TIMESTAMPTZ) AND CAST(p.eventEnd AS TIMESTAMPTZ)
WHERE m.filePublic = 'true';

INSERT INTO event_media (media_fk, event_fk)
SELECT DISTINCT m.mediaID, p.eventID
FROM src_media m JOIN published p ON p.deploymentID = m.deploymentID
     AND CAST(m.timestamp AS TIMESTAMPTZ) BETWEEN CAST(p.eventStart AS TIMESTAMPTZ) AND CAST(p.eventEnd AS TIMESTAMPTZ)
WHERE m.filePublic = 'true';
