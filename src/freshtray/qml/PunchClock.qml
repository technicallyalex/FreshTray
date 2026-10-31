import QtQuick
import QtQuick.Layouts
Item {
    id: clock
    implicitWidth: 240; implicitHeight: 196
    property bool animate: false
    property real feed: 0
    property date displayedTime: new Date()
    readonly property real hourAngle: (displayedTime.getHours()%12)*30+displayedTime.getMinutes()*.5
    readonly property real minuteAngle: displayedTime.getMinutes()*6
    readonly property real secondAngle: displayedTime.getSeconds()*6
    function captureTime() { displayedTime=new Date() }
    Accessible.role: Accessible.Graphic
    Accessible.name: "Time card clock showing " + Qt.formatTime(displayedTime,"h:mm:ss AP")
    Rectangle { anchors.centerIn: parent; width: 184; height: 184; radius: 92; color: Theme.selected }
    Rectangle { x: (parent.width-width)/2+5; y: 166; width: 146; height: 8; radius: 4; color: Theme.line; opacity: .45 }
    Rectangle {
        x: (parent.width-width)/2; y: 80; width: 148; height: 88; radius: 16
        gradient: Gradient { GradientStop { position: 0; color: "#1688e6" } GradientStop { position: 1; color: "#0067c7" } }
        Rectangle { id: cardSlot; anchors.horizontalCenter: parent.horizontalCenter; y: 5; width: 103; height: 7; radius: 3; color: "#053769" }
        Rectangle { objectName: "punchClockFace"; anchors.horizontalCenter: parent.horizontalCenter; y: (cardSlot.y+cardSlot.height+parent.height-height)/2; width: 44; height: 44; radius: 22; color: clock.animate && clock.feed>=.995 ? "#8ce3a6" : "white"
            Behavior on color { enabled: clock.animate; ColorAnimation { duration: 60 } }
            Item { x: 22; y: 22; width: 0; height: 0; rotation: clock.hourAngle
                Rectangle { x: -1; y: -11; width: 2; height: 11; radius: 1; color: "#073464" }
            }
            Item { x: 22; y: 22; width: 0; height: 0; rotation: clock.minuteAngle
                Rectangle { x: -1; y: -15; width: 2; height: 15; radius: 1; color: "#0075dd" }
            }
            Item { x: 22; y: 22; width: 0; height: 0; rotation: clock.secondAngle
                Rectangle { x: -.65; y: -17; width: 1.3; height: 20; radius: .65; color: "#d43c42" }
            }
            Rectangle { anchors.centerIn: parent; width: 4; height: 4; radius: 2; color: "#073464" }
        }
    }
    // The card overlays the cabinet's top edge and is clipped at the slot's
    // opening. The front lip then covers its cut edge, giving a true feed path.
    Item {
        x: 0; y: 0; width: parent.width; height: 89; clip: true
        Canvas {
            id: card
            x: (parent.width-width)/2; y: 18+clock.feed*40
            width: 92; height: 70
            onPaint: {
                const c=getContext("2d"); c.reset()
                // A clipped-corner data card, with real transparent punched holes.
                c.beginPath(); c.moveTo(.5,.5); c.lineTo(width-10.5,.5)
                c.lineTo(width-.5,10.5); c.lineTo(width-.5,height-3.5)
                c.quadraticCurveTo(width-.5,height-.5,width-3.5,height-.5)
                c.lineTo(3.5,height-.5); c.quadraticCurveTo(.5,height-.5,.5,height-3.5)
                c.closePath(); c.fillStyle="#fffef7"; c.fill()
                c.strokeStyle="#b9c8d4"; c.lineWidth=1; c.stroke()
                const pattern=["101001010","010110001","100010100","001101010","110000101","001010010","100101100"]
                for(let row=0;row<pattern.length;row++) {
                    for(let col=0;col<pattern[row].length;col++) {
                        const x=9+col*8.5, y=11+row*7.5
                        if(pattern[row][col]==="1") {
                            c.globalCompositeOperation="destination-out"
                            c.fillStyle="black"; c.fillRect(x,y,4,4.5)
                        } else {
                            c.globalCompositeOperation="source-over"
                            c.fillStyle="#d7dedc"; c.fillRect(x+1.5,y+1.5,1,1)
                        }
                    }
                }
                c.globalCompositeOperation="source-over"
            }
        }
    }
    Rectangle { x: (parent.width-width)/2; y: 88; width: 103; height: 4; radius: 2; color: "#053769" }
    SequentialAnimation on feed {
        running: clock.animate; loops: Animation.Infinite
        PauseAnimation { duration: 1000 }
        NumberAnimation { to: 1; duration: 850; easing.type: Easing.InOutCubic }
        PauseAnimation { duration: 150 }
        NumberAnimation { to: 0; duration: 1100; easing.type: Easing.InOutCubic }
        PauseAnimation { duration: 700 }
    }
    onAnimateChanged: if(!animate) feed=0
}
