-- A made-up point count: one event per site visit, one occurrence per species counted there.
DELETE FROM occurrence;
DELETE FROM event;

INSERT INTO event (event_pk, eventID, eventCategory, eventDate, decimalLatitude, decimalLongitude, recordedBy)
SELECT site || ':' || date, site || ':' || date, 'survey', date, CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), observer
FROM src_sites;

INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, scientificName, occurrenceStatus, organismQuantity, organismQuantityType)
SELECT c.site || ':' || s.date || ':' || c.species, c.site || ':' || s.date || ':' || c.species, c.site || ':' || s.date,
       c.species, CASE WHEN c.count = '0' THEN 'notDetected' ELSE 'detected' END, c.count, 'individuals'
FROM src_counts c JOIN src_sites s ON s.site = c.site;
