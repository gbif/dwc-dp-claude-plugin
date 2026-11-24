-- Satellite-tracked humpback whales (Movebank study 3030068329, three of its 50 whales).
-- Load first: locations.csv as src_locations, reference-data.csv as src_reference (load --as reference).
-- See references/recipes/tracking.md.
--
-- Agreed with the data holder:
--   * the raw Argos locations become occurrences, without those flagged as outliers
--     (visible = false); the locations estimated by the state-space model stay out;
--   * every location is kept: no thinning;
--   * coordinateUncertaintyInMeters from the Argos location class, as the upper bound of its
--     nominal accuracy: 3 = 250 m, 2 = 500 m, 1 = 1500 m; classes 0, A and B have none.
-- Chosen for this example, as the recipe proposes:
--   * a study event, one deployment event per tag on an animal under it, and under each deployment
--     a tag attachment event and one event per location;
--   * each whale is an organism; every occurrence points to it; its name is one identification of
--     the organism;
--   * sex on every occurrence, life stage only on the tag attachment (Movebank records it for the
--     start of the deployment); sex 'u' (unknown) stays empty;
--   * the tag is an agent (agentType 'machine') with the role 'recorded by' in its deployment;
--   * deployment attributes without a field are assertions about the deployment, typed with their
--     Movebank attribute IRIs (NERC MVB), which the data's README gives.

DELETE FROM event_assertion;
DELETE FROM organism_assertion;
DELETE FROM event_agent_role;
DELETE FROM agent;
DELETE FROM identification;
DELETE FROM occurrence;
DELETE FROM organism;
DELETE FROM event;

-- The locations kept, with their deployment.
CREATE OR REPLACE TEMP TABLE fixes AS
SELECT l.*, r."deployment-id" AS deployment
FROM src_locations l JOIN src_reference r ON r."animal-id" = l."individual-local-identifier"
WHERE l.modelled IS NULL AND l.visible = 'true';

-- 1. Events: the study, the deployments, the tag attachments and the locations.
INSERT INTO event (event_pk, eventCategory, eventType, eventDate)
SELECT 'study', 'context', 'Project',
       min(substr("deploy-on-date", 1, 10)) || '/' || max(substr("deploy-off-date", 1, 10))
FROM src_reference;

-- A deployment lasts from deploy-on to deploy-off. Their times are 00:00:00 and 23:59:59, which
-- mark whole days, so the dates are written without times.
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventType, eventDate)
SELECT "deployment-id", "deployment-id", 'study', 'context', 'Sensor',
       substr("deploy-on-date", 1, 10) || '/' || substr("deploy-off-date", 1, 10)
FROM src_reference;

INSERT INTO event (event_pk, parentEvent_fk, eventCategory, eventType, eventDate,
                   decimalLatitude, decimalLongitude, geodeticDatum)
SELECT "deployment-id" || ':attachment', "deployment-id", 'occurrence', 'Observation', substr("deploy-on-date", 1, 10),
       CAST("deploy-on-latitude" AS DOUBLE), CAST("deploy-on-longitude" AS DOUBLE), 'WGS84'
FROM src_reference;

-- One event per location. Movebank's event-id is its identifier. Times are UTC.
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventType, eventDate,
                   decimalLatitude, decimalLongitude, geodeticDatum, coordinateUncertaintyInMeters,
                   georeferenceProtocol, georeferenceRemarks)
SELECT "event-id", "event-id", deployment, 'occurrence', 'Observation',
       replace(substr(timestamp, 1, 19), ' ', 'T') || 'Z',
       CAST("location-lat" AS DOUBLE), CAST("location-long" AS DOUBLE), 'WGS84',
       CASE "argos:lc" WHEN '3' THEN 250 WHEN '2' THEN 500 WHEN '1' THEN 1500 END,
       'Argos Doppler location (' || "argos:location-algorithm" || '); uncertainty is the upper bound of the nominal accuracy of the Argos location class (3: 250 m, 2: 500 m, 1: 1500 m; none for 0, A, B)',
       'Argos location class ' || "argos:lc"
FROM fixes;

-- 2. The whales, their names and traits.
INSERT INTO organism (organism_pk, organismID, organismScope)
SELECT "animal-id", "animal-id", 'multicellular organism' FROM src_reference;

INSERT INTO identification (identification_pk, identificationID, organism_fk, isAcceptedIdentification, scientificName)
SELECT "animal-id" || ':id', "animal-id" || ':id', "animal-id", true, "animal-taxon" FROM src_reference;

INSERT INTO organism_assertion (assertionID, organism_fk, verbatimAssertionType, assertionType, assertionTypeIRI, assertionValue)
SELECT "animal-id" || ':group', "animal-id", 'animal-group-id', 'animal group ID',
       'http://vocab.nerc.ac.uk/collection/MVB/current/MVB000340/', "animal-group-id"
FROM src_reference WHERE nullif("animal-group-id", '') IS NOT NULL;

-- 3. Occurrences: the whale at its tagging, and at each location.
INSERT INTO occurrence (occurrence_pk, event_fk, organism_fk, occurrenceStatus, sex, lifeStage)
SELECT "deployment-id" || ':attachment', "deployment-id" || ':attachment', "animal-id", 'detected',
       CASE "animal-sex" WHEN 'm' THEN 'male' WHEN 'f' THEN 'female' END, "animal-life-stage"
FROM src_reference;

INSERT INTO occurrence (occurrence_pk, event_fk, organism_fk, occurrenceStatus, sex)
SELECT f."event-id", f."event-id", f."individual-local-identifier", 'detected',
       CASE r."animal-sex" WHEN 'm' THEN 'male' WHEN 'f' THEN 'female' END
FROM fixes f JOIN src_reference r ON r."animal-id" = f."individual-local-identifier";

-- 4. The tags, as the agents that recorded the locations of their deployment.
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT 'tag:' || "tag-id", 'machine',
       concat_ws(' ', "tag-manufacturer-name", "tag-model", 'tag', "tag-id")
FROM src_reference;

INSERT INTO event_agent_role (event_fk, agent_fk, agentRole, agentRoleOrder)
SELECT "deployment-id", 'tag:' || "tag-id", 'recorded by', 1 FROM src_reference;

-- 5. How each tag was deployed: Movebank deployment attributes without a DwC-DP field.
INSERT INTO event_assertion (assertionID, event_fk, verbatimAssertionType, assertionType, assertionTypeIRI, assertionValue)
SELECT r."deployment-id" || ':' || a.verbatim, r."deployment-id", a.verbatim, a.type,
       'http://vocab.nerc.ac.uk/collection/MVB/current/' || a.mvb || '/', a.value
FROM src_reference r,
     LATERAL (VALUES ('attachment-type', 'attachment type', 'MVB000052', r."attachment-type"),
                     ('duty-cycle', 'duty cycle', 'MVB000086', r."duty-cycle"),
                     ('manipulation-type', 'manipulation type', 'MVB000155', r."manipulation-type"),
                     ('tag-readout-method', 'tag readout method', 'MVB000188', r."tag-readout-method"),
                     ('outlier-comments', 'outlier comments', 'MVB000374', r."outlier-comments"))
       AS a(verbatim, type, mvb, value)
WHERE nullif(a.value, '') IS NOT NULL;
