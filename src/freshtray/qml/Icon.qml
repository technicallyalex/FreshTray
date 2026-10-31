import QtQuick
Canvas {
    id: icon
    property string name: "calendar"
    property color ink: Theme.ink
    implicitWidth: 18; implicitHeight: 18
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        const c=getContext("2d"); c.reset(); c.scale(width/24,height/24)
        c.strokeStyle=ink; c.lineWidth=1.7; c.lineCap="round"; c.lineJoin="round"
        c.beginPath()
        if(name==="calendar") {
            c.roundedRect(3,5,18,16,2,2); c.moveTo(3,10); c.lineTo(21,10)
            c.moveTo(8,3); c.lineTo(8,7); c.moveTo(16,3); c.lineTo(16,7)
            c.moveTo(7,14); c.lineTo(10,14); c.moveTo(14,14); c.lineTo(17,14)
            c.moveTo(7,18); c.lineTo(10,18)
        } else if(name==="left") { c.moveTo(14,6); c.lineTo(8,12); c.lineTo(14,18)
        } else if(name==="right") { c.moveTo(10,6); c.lineTo(16,12); c.lineTo(10,18)
        } else if(name==="down") { c.moveTo(7,10); c.lineTo(12,15); c.lineTo(17,10)
        } else if(name==="close") { c.moveTo(6,6); c.lineTo(18,18); c.moveTo(18,6); c.lineTo(6,18)
        } else if(name==="minimize") { c.moveTo(5,15); c.lineTo(19,15)
        } else if(name==="maximize") { c.rect(5,5,14,14)
        } else if(name==="check") { c.moveTo(5,12); c.lineTo(10,17); c.lineTo(19,7)
        } else if(name==="plus") { c.moveTo(5,12); c.lineTo(19,12); c.moveTo(12,5); c.lineTo(12,19)
        } else { c.arc(12,12,9,0,Math.PI*2); c.moveTo(12,6); c.lineTo(12,12); c.lineTo(16,14) }
        c.stroke()
    }
}
