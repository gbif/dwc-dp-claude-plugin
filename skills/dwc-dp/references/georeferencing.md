# Georeferencing: footprints, points with a radius, and UTM

Read this when places are given as shapes (routes, transects, plots, polygons), as UTM or other
projected coordinates, or when they have no coordinates yet. The fields are `event`'s; `describe
event` lists them all.

## What the event can hold

- **A point with a radius:** `decimalLatitude`, `decimalLongitude`, `geodeticDatum`, and
  `coordinateUncertaintyInMeters`, a circle that holds the whole place.
- **A footprint:** the shape itself as WKT in `footprintWKT`, with its reference system in
  `footprintSRS`. The schema's notes say a place "may have both a point-radius representation …
  and a footprint representation". Keep the shape whenever they have one: it says more than any
  circle.
- **How it was done:** `georeferenceProtocol`, `georeferenceSources`, `georeferencedBy`,
  `georeferencedDate` and `georeferenceRemarks`.
- **As written:** `verbatimCoordinates`, `verbatimCoordinateSystem` and `verbatimSRS`, such as
  `32U 724000 6176000`, `UTM` and `EPSG:25832`.

## The helpers

`run` and `sql` have five functions for this, written in Python in `dwcdp.py`. They need no DuckDB
extension and no network.

| Function | Returns |
|---|---|
| `wkt_center_lat(wkt)`, `wkt_center_lon(wkt)` | the center of a WKT point, line or polygon, single or multi: the mean of points, the length-weighted center of lines, the area-weighted center of polygons (holes taken out) |
| `wkt_radius_m(wkt)` | metres from that center to the farthest vertex, rounded up: a circle that holds the whole shape |
| `utm_lat(zone, hemisphere, easting, northing)`, `utm_lon(...)` | latitude and longitude from UTM, such as `utm_lat(32, 'N', easting, northing)` |

For example, a trip along a route:

```sql
SELECT trip, route AS footprintWKT, 'EPSG:4326' AS footprintSRS,
       round(wkt_center_lat(route), 5) AS decimalLatitude,
       round(wkt_center_lon(route), 5) AS decimalLongitude,
       wkt_radius_m(route) AS coordinateUncertaintyInMeters
FROM src_trips;
```

A value they can't read stops `run` with the function's name and the value, such as a WKT that
isn't a point, line or polygon, or a UTM zone outside 1–60.

## What the helpers don't decide

- **The method is theirs.** A center and a radius to the farthest point is one way to make a
  point-radius from a shape. Show them the center and the radius for a few records, and use it only
  with their agreement. Then say how in `georeferenceProtocol`, for example "center of the route
  line, weighted by length; radius to its farthest vertex".
- **The center can lie off the shape.** For a bent route or a crescent-shaped plot, the center may
  fall outside it. The circle still holds the whole shape. If they want a point on the shape
  instead, that's another rule, to agree on.
- **Other uncertainty adds to the radius.** The radius covers only the shape. GPS error, map scale
  and an unknown datum add to it, by a rule they agree to. The schema's examples for
  `coordinateUncertaintyInMeters` give `30` as "reasonable lower limit … of a GPS reading under
  good conditions if the actual precision was not recorded at the time".
- **Large shapes.** The center is computed on a flat projection around the shape's mean latitude,
  which suits shapes up to some tens of kilometres. A shape that crosses the antimeridian is
  refused.

## UTM and the datum

UTM coordinates are converted on the GRS80 ellipsoid, which ETRS89, NAD83 and (to 0.1 mm) WGS84
use. Krüger's series is used to the third order, accurate to about a millimetre within a zone.

**Converting the projection doesn't change the datum.** UTM coordinates in ETRS89 (such as
EPSG:25832, ETRS89 / UTM zone 32N) give latitude and longitude in ETRS89, so `geodeticDatum` is
`EPSG:4258`, not WGS84. ETRS89 and WGS84 now differ by about a metre in Europe, and a datum is
never relabelled without their agreement.

**Other ellipsoids are not supported.** Coordinates on another ellipsoid, such as ED50 (European
1950) on the International 1924 ellipsoid or NAD27 on Clarke 1866, can't be converted here. Changing
their datum also needs a transformation this tool doesn't have. Keep them in
`verbatimCoordinates`, `verbatimCoordinateSystem` and `verbatimSRS`, and ask the data holder how
they want them converted.

Ask which datum and zone their UTM coordinates are in. A zone number alone doesn't say the
hemisphere or the datum.

## Places without coordinates

A place name can be looked up in a gazetteer, or coordinates turned into a place name (reverse
geocoding), only with their agreement. It sends their places to the service (SKILL.md, "Nothing
leaves their machine"). Keep the results in a file in their folder, load it like their other files,
and name the source in `georeferenceSources`.

## Sources

- DwC-DP 1.0 table schema `event` (the vendored copy): the georeferencing fields, their notes and
  examples.
- Krüger's series for the transverse Mercator projection, as given by Karney (2011),
  https://doi.org/10.1007/s00190-011-0445-3, and the UTM parameters: scale 0.9996 on the central
  meridian, false easting 500,000 m, false northing 10,000,000 m in the southern hemisphere.
- GRS80: semi-major axis 6,378,137 m, flattening 1/298.257222101.
