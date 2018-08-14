import sys
import svgpath.parser as parser

PRELIM = """// OpenSCAD file automatically generated by svg2cookiercutter.py
wallHeight = 12;
minWallThickness = 2;
maxWallThickness = 3;
minInsideWallThickness = 1;
maxInsideWallThickness = 3;

wallFlareWidth = 5;
wallFlareThickness = 3;
insideWallFlareWidth = 5;
insideWallFlareThickness = 3;

featureHeight = 8;
minFeatureThickness = 1;
maxFeatureThickness = 3;

connectorThickness = 3;
cuttingEdgeThickness = 1.5;

size = $OVERALL_SIZE$;

scale = size/$OVERALL_SIZE$;

module ribbon(points, thickness=1) {
    union() {
        for (i=[1:len(points)-1]) {
            hull() {
                translate(points[i-1]) circle(d=thickness, $fn=8);
                translate(points[i]) circle(d=thickness, $fn=8);
            }
        }
    }
}


module wall(points,height,thickness) {
    render(convexity=10) union() {
        for (i=[1:len(points)-1]) {
            hull() {
                translate(points[i-1]) cylinder(h=height,d1=thickness,d2=cuttingEdgeThickness,$fn=4);
                translate(points[i])   cylinder(h=height,d1=thickness,d2=cuttingEdgeThickness,$fn=4);
            }
        }
    }
}


module outerFlare(path) {
  difference() {
    render(convexity=10) linear_extrude(height=wallFlareThickness) ribbon(path,thickness=wallFlareWidth);
    translate([0,0,-0.01]) linear_extrude(height=wallFlareThickness+0.02) polygon(points=path);
  }
}

module innerFlare(path) {
  intersection() {
    render(convexity=10) linear_extrude(height=insideWallFlareThickness) ribbon(path,thickness=insideWallFlareWidth);
    translate([0,0,-0.01]) linear_extrude(height=insideWallFlareThickness+0.02) polygon(points=path);
  }
}

module connector(path,height) {
  render(convexity=10) linear_extrude(height=height) polygon(points=path);
}

module cookieCutter() {
"""

def isRed(rgb):
    return rgb is not None and rgb[0] >= 0.4 and rgb[1]+rgb[2] < rgb[0] * 0.25

def isGreen(rgb):
    return rgb is not None and rgb[1] >= 0.4 and rgb[0]+rgb[2] < rgb[1] * 0.25

def isBlack(rgb):
    return rgb is not None and rgb[0]+rgb[1]+rgb[2]<0.2

class Line(object):
    def __init__(self, points, base, stroke, strokeWidth):
        self.points = points
        self.base = base
        self.stroke = stroke
        self.strokeWidth = strokeWidth

    def toCode(self, pathCount):
        code = []
        path = 'path'+str(pathCount)
        code.append( path + ' = scale * [' + ','.join(('[%.3f,%.3f]'%tuple(p) for p in self.points)) + '];' );
        if self.stroke:
            code.append('wall('+path+','+self.height+','+self.width+');')
            if self.hasOuterFlare:
                code.append('outerFlare('+path+');')
            elif self.hasInnerFlare:
                code.append('innerFlare('+path+');')
        if self.base:
            code.append('connector('+path+','+self.baseHeight+');')
        code.append('') # will add a newline
        return code

# width="0.5", base=False, stroke=False):
class OuterWall(Line):
    def __init__(self, points, base, stroke, strokeWidth):
        super().__init__(points, base, stroke, strokeWidth)
        self.height = "wallHeight"
        self.width = "min(maxWallThickness,max(%.3f,minWallThickness))" % self.strokeWidth
        self.baseHeight = "wallHeight"
        self.hasOuterFlare = True
        self.hasInnerFlare = False

class InnerWall(Line):
    def __init__(self, points, base, stroke, strokeWidth):
        super().__init__(points, base, stroke, strokeWidth)
        self.height = "wallHeight"
        self.width = "min(maxInsideWallThickness,max(%.3f,minInsideWallThickness))" % self.strokeWidth
        self.baseHeight = "wallHeight"
        self.hasOuterFlare = False
        self.hasInnerFlare = True

class Feature(Line):
    def __init__(self, points, base, stroke, strokeWidth):
        super().__init__(points, base, stroke, strokeWidth)
        self.height = "featureHeight"
        self.width = "min(maxFeatureThickness,max(%.3f,minFeatureThickness))" % self.strokeWidth
        self.baseHeight = "featureHeight"
        self.hasOuterFlare = False
        self.hasInnerFlare = False

class Connector(Line):
    def __init__(self, points, base):
        super().__init__(points, base, False, None) # no stroke for connectors, thus no use of self.height and self.width
        self.baseHeight = "connectorThickness"
        self.hasOuterFlare = False
        self.hasInnerFlare = False

def svgToCookieCutter(filename, tolerance=0.1, strokeAll = False):
    code = [PRELIM]
    pathCount = 0;
    minXY = [float("inf"), float("inf")]
    maxXY = [float("-inf"), float("-inf")]

    for superpath in parser.getPathsFromSVGFile(filename)[0]:
        for path in superpath.breakup():
            base = path.svgState.fill is not None
            stroke = strokeAll or path.svgState.stroke is not None
            if not stroke and not base: continue

            lines = path.linearApproximation(error=tolerance)
            points = [(-l.start.real,l.start.imag) for l in lines]
            points.append((-lines[-1].end.real, lines[-1].end.imag))

            if isRed    (path.svgState.fill) or isRed  (path.svgState.stroke):
                line = OuterWall(points, base, stroke, path.svgState.strokeWidth)
            elif isGreen(path.svgState.fill) or isGreen(path.svgState.stroke):
                line = InnerWall(points, base, stroke, path.svgState.strokeWidth)
            elif isBlack(path.svgState.fill) or isBlack(path.svgState.stroke):
                line = Feature(points, base, stroke, path.svgState.strokeWidth)
            else:
                line = Connector(points, base)

            for i in range(2):
                minXY[i] = min(minXY[i], min(p[i] for p in line.points))
                maxXY[i] = max(maxXY[i], max(p[i] for p in line.points))

            code += line.toCode(pathCount)
            pathCount += 1

    size = max(maxXY[0]-minXY[0], maxXY[1]-minXY[1])

    code.append('}\n')
    code.append('translate([%.3f*scale + wallFlareWidth/2,  %.3f*scale + wallFlareWidth/2,0]) cookieCutter();' % (-minXY[0],-minXY[1]))

    return '\n'.join(code).replace('$OVERALL_SIZE$', '%.3f' % size)

if __name__ == '__main__':
    print(svgToCookieCutter(sys.argv[1]))
