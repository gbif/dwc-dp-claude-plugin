-- Point counts (made up): a project with repeated 10-minute visits to two points.
-- Load first: sites.csv, visits.csv, counts.csv as src_sites, src_visits, src_counts.
-- The choices marked "agreed" are the data holder's; see references/recipes/survey.md.

DELETE FROM occurrence;
DELETE FROM survey_survey_target;
DELETE FROM survey_target_descriptor;
DELETE FROM survey_target;
DELETE FROM survey;
DELETE FROM event;

-- The project: the parent event of every visit. Its dates span the visits.
-- Agreed: eventCategory 'context' (a frame for the visits, not itself a count), eventType 'Project'.
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, eventRemarks)
SELECT 'PC2025', 'PC2025', 'context', 'Project', min(date) || '/' || max(date),
       'Point counts, made up for testing.'
FROM src_visits;

-- One event per visit, with the place taken from its site.
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventType, eventDate, eventTime,
                   locality, habitat, decimalLatitude, decimalLongitude, recordedBy)
SELECT v.visit, v.visit, 'PC2025', 'survey', 'SiteVisit', v.date, v.start,
       v.site, s.habitat, CAST(s.lat AS DOUBLE), CAST(s.lon AS DOUBLE), v.observer
FROM src_visits v JOIN src_sites s ON s.site = v.site;

-- What was looked for: every bird species except gulls. One target, used by every visit.
-- Agreed: the protocol says all counts of it are reported, so absence can be inferred.
INSERT INTO survey_target (surveyTarget_pk, surveyTargetID, surveyTargetDescription, isSurveyTargetFullyReported)
VALUES ('birds-except-gulls', 'birds-except-gulls', 'all bird species except gulls (Larus)', true);

INSERT INTO survey_target_descriptor (surveyTarget_fk, surveyTargetType, surveyTargetValue, includeOrExclude)
VALUES ('birds-except-gulls', 'taxon', 'Aves', 'include'),
       ('birds-except-gulls', 'taxon', 'Larus', 'exclude');

-- Each visit is a survey: the level at which the method and the effort apply (agreed).
-- Left empty, because the protocol doesn't say: taxonCompletenessReported, and
-- areNonTargetTaxaFullyReported (other animals are noted only "when seen").
INSERT INTO survey (survey_pk, surveyID, event_fk, samplingProtocol, samplingPerformedBy,
                    isSamplingEffortReported, samplingEffortValue, samplingEffortUnit,
                    isAbundanceReported, isAbsenceReported, hasNonTargetTaxa, nonTargetTaxa)
SELECT 'survey:' || v.visit, 'survey:' || v.visit, v.visit, '10-minute point count', v.observer,
       true, CAST(v.minutes AS DOUBLE), 'minutes',
       true, true,
       EXISTS (SELECT 1 FROM src_counts c WHERE c.visit = v.visit AND c.species IN ('Larus canus', 'Lepus europaeus')),
       (SELECT string_agg(c.species, ' | ' ORDER BY c.species) FROM src_counts c
         WHERE c.visit = v.visit AND c.species IN ('Larus canus', 'Lepus europaeus'))
FROM src_visits v;

INSERT INTO survey_survey_target (survey_fk, surveyTarget_fk)
SELECT 'survey:' || visit, 'birds-except-gulls' FROM src_visits;

-- One occurrence per species counted on a visit. A count of 0 is a species looked for and not
-- found. Agreed: the gull and the hare are outside the target, so they point to no target.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, surveyTarget_fk, scientificName,
                        occurrenceStatus, organismQuantity, organismQuantityType, occurrenceRemarks)
SELECT c.visit || ':' || c.species, c.visit || ':' || c.species, c.visit,
       CASE WHEN c.species IN ('Larus canus', 'Lepus europaeus') THEN NULL ELSE 'birds-except-gulls' END,
       c.species,
       CASE WHEN c.count = '0' THEN 'notDetected' ELSE 'detected' END,
       c.count, 'individuals', c.note
FROM src_counts c;
