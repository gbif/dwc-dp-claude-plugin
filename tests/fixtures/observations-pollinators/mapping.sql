-- Pollinator observations (made up): flowers and their visitors, with photos.
-- Load first: observations.csv and photos.csv as src_observations and src_photos.
-- The choices marked "agreed" are the data holder's; see references/recipes/observations.md.

DELETE FROM media_agent_role;
DELETE FROM occurrence_media;
DELETE FROM media;
DELETE FROM agent;
DELETE FROM organism_interaction;
DELETE FROM identification;
DELETE FROM occurrence;
DELETE FROM event;

-- One event per place and moment. Agreed: rows with the same date, time and coordinates were seen
-- together, so a flower and its visitor share an event. eventCategory 'occurrence' (agreed).
-- The notebook doesn't say which geodetic datum the coordinates use, so it is 'not recorded', as the
-- schema's notes for geodeticDatum say.
-- The date and time go together in eventDate, as ISO 8601 writes them.
INSERT INTO event (event_pk, eventID, eventCategory, eventDate, locality,
                   decimalLatitude, decimalLongitude, geodeticDatum, recordedBy)
SELECT DISTINCT place || ' ' || date || 'T' || time, place || ' ' || date || 'T' || time, 'occurrence',
       date || 'T' || time, place, CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), 'not recorded', observer
FROM src_observations;

-- One occurrence per row of the notebook.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus,
                        organismQuantity, organismQuantityType, sex, behavior)
SELECT obs, obs, place || ' ' || date || 'T' || time, 'detected',
       count, 'individuals', nullif(sex, ''), nullif(behaviour, '')
FROM src_observations;

-- The name of each occurrence, as an identification based on it.
INSERT INTO identification (identification_pk, identificationID, occurrence_fk, isAcceptedIdentification, scientificName)
SELECT obs || ':id', obs || ':id', obs, true, species FROM src_observations;

-- A visitor on a flower. The visitor acts, so it is the subject; the flower is the related
-- occurrence (schema notes of organism-interaction). Agreed: type 'visited flower of', one of the
-- schema's examples, and the related part 'flower'.
INSERT INTO organism_interaction (organismInteraction_pk, organismInteractionID, event_fk,
                                  subjectOccurrence_fk, organismInteractionType, relatedOccurrence_fk,
                                  relatedOrganismPart)
SELECT obs || '>' || visits_obs, obs || '>' || visits_obs, place || ' ' || date || 'T' || time,
       obs, 'visited flower of', visits_obs, 'flower'
FROM src_observations
WHERE visits_obs IS NOT NULL;

-- The photographers, as agents, so that they can be credited as the photos' creators.
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT DISTINCT lower(replace(photographer, ' ', '-')), 'person', photographer FROM src_photos;

-- The photos: the URL is both the identifier and where to get the file.
INSERT INTO media (media_pk, mediaID, mediaType, accessURI, license)
SELECT photo, photo, 'StillImage', photo, license FROM src_photos;

INSERT INTO media_agent_role (media_fk, agent_fk, agentRole, agentRoleOrder)
SELECT photo, lower(replace(photographer, ' ', '-')), 'creator', 1 FROM src_photos;

-- Which occurrence each photo shows.
INSERT INTO occurrence_media (media_fk, occurrence_fk)
SELECT photo, obs FROM src_observations WHERE photo IS NOT NULL;
