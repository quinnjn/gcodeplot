import sys
import svgpath.parser as parser

PRELIM = """// OpenSCAD file automatically generated by svg2cookiercutter.py
wallHeight = 10;
wallBaseWidth = 3;
wallBaseThickness = 1.5;
minWallThickness = 1;
maxWallThickness = 3;
insideWallBaseWidth = 2;
insideWallBaseThickness = 1.5;
minInsideWallThickness = 1;
maxInsideWallThickness = 3;
featureHeight = 6;
minFeatureThickness = 0.8;
maxFeatureThickness = 3;
featureHolderThickness = 1;
size = $OVERALL_SIZE$;

module dummy() {}

scale = size/$OVERALL_SIZE$;

module ribbon(points, thickness=1, closed=false) {
    p = closed ? concat(points, [points[0]]) : points;
    
    union() {
        for (i=[1:len(p)-1]) {
            hull() {
                translate(p[i-1]) circle(d=thickness, $fn=8);
                translate(p[i]) circle(d=thickness, $fn=8);
            }
        }
    }
}

module cookieCutter() {
"""

class Line(object):
    def __init__(self, height="featureHeight", width="0.5", base=False, wall=False, insideWall=False):
        self.height = height
        self.width = width
        self.base = base
        self.wall = wall
        self.insideWall = insideWall
        self.points = []
        
    def toCode(self, pathCount):
        code = []
        path = 'path'+str(pathCount)
        code.append( path + '=scale*[' + ','.join(('[%.3f,%.3f]'%tuple(p) for p in self.points)) + '];' );
        if not self.base:
            code.append('render(convexity=10) linear_extrude(height=('+self.height+')) ribbon('+path+',thickness='+self.width+');')
            if self.wall:
                baseRibbon = 'render(convexity=10) linear_extrude(height=wallBaseThickness) ribbon('+path+',thickness=wallBaseWidth);'
                code.append('difference() {')
                code.append(' ' + baseRibbon);
                code.append(' translate([0,0,-0.01]) linear_extrude(height=wallBaseThickness+0.02) polygon(points='+path+');')
                code.append('}')
            elif self.insideWall:
                baseRibbon = 'render(convexity=10) linear_extrude(height=insideWallBaseThickness) ribbon('+path+',thickness=insideWallBaseWidth);'
                code.append('intersection() {')
                code.append(' ' + baseRibbon);
                code.append(' translate([0,0,-0.01]) linear_extrude(height=insideWallBaseThickness+0.02) polygon(points='+path+');')
                code.append('}')
        else:
            code.append('render(convexity=10) linear_extrude(height=featureHolderThickness) polygon(points='+path+');')
        return code
        
def isRed(rgb):
    return rgb is not None and rgb[0] >= 0.4 and rgb[1]+rgb[2] < rgb[0] * 0.25

def isGreen(rgb):
    return rgb is not None and rgb[1] >= 0.4 and rgb[0]+rgb[2] < rgb[1] * 0.25

def svgToCookieCutter(filename, tolerance=0.1, strokeAll = False):
    code = [PRELIM]
    pathCount = 0;
    minXY = [float("inf"), float("inf")]
    maxXY = [float("-inf"), float("-inf")]
    
    for superpath in parser.getPathsFromSVGFile(filename)[0]:
        for path in superpath.breakup():
            line = Line()
            
            if path.svgState.fill is not None:
                line.base = True
            elif strokeAll or path.svgState.stroke is not None:
                line.base = False
                if isRed(path.svgState.stroke):
                    line.width = "min(maxWallThickness,max(%.3f,minWallThickness))" % path.svgState.strokeWidth
                    line.height = "wallHeight"
                    line.wall = True
                elif isGreen(path.svgState.stroke):
                    line.width = "min(maxInsideWallThickness,max(%.3f,minInsideWallThickness))" % path.svgState.strokeWidth
                    line.height = "wallHeight"
                    line.insideWall = True
                else:
                    line.width = "min(maxFeatureThickness,max(%.3f,minFeatureThickness))" % path.svgState.strokeWidth
                    line.height = "featureHeight"
                    line.wall = False
            else:
                continue
                
            lines = path.linearApproximation(error=tolerance)
            
            line.points = [(l.start.real,l.start.imag) for l in lines]
            line.points.append((lines[-1].end.real, lines[-1].end.imag))
            
            for i in range(2):
                minXY[i] = min(minXY[i], min(p[i] for p in line.points))
                maxXY[i] = max(maxXY[i], max(p[i] for p in line.points))
                
            code += line.toCode(pathCount)
            pathCount += 1

    size = max(maxXY[0]-minXY[0], maxXY[1]-minXY[1])
    
    code.append('}\n')
    code.append('translate([%.3f*scale,%.3f*scale,0]) cookieCutter();' % (-minXY[0],-minXY[1]))
            
    return '\n'.join(code).replace('$OVERALL_SIZE$', '%.3f' % size)
    
if __name__ == '__main__':
    print(svgToCookieCutter(sys.argv[1]))
    