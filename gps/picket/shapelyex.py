import json
from shapely.geometry import shape, Point
# depending on your version, use: from shapely.geometry import shape, Point

# load GeoJSON file containing sectors
with open('geo.json') as f:
	js = json.load(f)

# construct point based on lon/lat returned by geocoder
# in keepin, in keepout = no drive
#point = Point(0.57714, 51.7095)

# in keepin, not in keepout = drive OK
#point = Point(0.577412, 51.7102550)

# not in keepin, not in keepout = no drive
#point = Point(0.57776123, 51.7099326)

# not in keepin, in keepout = no drive
point = Point(0.576739311, 51.70924785)



# check each polygon to see if it contains the point
drive = False
user_drive = False
for feature in js['features']:
	polygon = shape(feature['geometry'])
	if polygon.contains(point):
		if feature['properties']['type'] == "keepin":
			print('Point was found inside level '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
			drive = True

for feature in js['features']:
        polygon = shape(feature['geometry'])
        if polygon.contains(point):
                if feature['properties']['type'] == "keepout":
                        print('Point was found inside level '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will NOT be able to drive regardless of other conditions')
                        drive = False

print('End result is drive=',str(drive))
