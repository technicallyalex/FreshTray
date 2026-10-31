import QtQuick

// Paint only the border: text, fields and panel fills never fade.
Canvas {
    id: outline
    property color lineColor: Theme.line
    property real radius: 9
    property bool fading: true
    onLineColorChanged: requestPaint()
    onRadiusChanged: requestPaint()
    onFadingChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if(visible) requestPaint()
    onPaint: {
        const c=getContext("2d"); c.reset()
        if(width<1 || height<1) return
        const x=.5, y=.5, right=width-.5, bottom=height-.5
        const r=Math.max(0,Math.min(radius,(width-1)/2,(height-1)/2))
        c.beginPath(); c.moveTo(x+r,y); c.lineTo(right-r,y)
        c.quadraticCurveTo(right,y,right,y+r); c.lineTo(right,bottom-r)
        c.quadraticCurveTo(right,bottom,right-r,bottom); c.lineTo(x+r,bottom)
        c.quadraticCurveTo(x,bottom,x,bottom-r); c.lineTo(x,y+r)
        c.quadraticCurveTo(x,y,x+r,y); c.closePath()
        if(fading) {
            function ink(alpha) {
                return "rgba("+Math.round(lineColor.r*255)+","+Math.round(lineColor.g*255)+","+Math.round(lineColor.b*255)+","+(lineColor.a*alpha)+")"
            }
            const gradient=c.createLinearGradient(0,0,0,height)
            gradient.addColorStop(0,ink(1)); gradient.addColorStop(.18,ink(1))
            gradient.addColorStop(.52,ink(.6)); gradient.addColorStop(.88,ink(0))
            gradient.addColorStop(1,ink(0)); c.strokeStyle=gradient
        } else c.strokeStyle=lineColor
        c.lineWidth=1; c.stroke()
    }
}
