import QtQuick
import QtQuick.Layouts
Item {
    id: face
    property string kind: "digital"
    property bool active: visible
    property var timerState: backend.workTimer.state
    property real seconds: 0
    property bool running: timerState.status==="running"
    readonly property bool analog: kind==="analog" || kind==="station"
    readonly property string durationText: formatDuration(seconds)
    readonly property string digits: durationText.replace(/:/g,"")
    readonly property bool animating: active && visible && running
    implicitWidth: 200
    implicitHeight: analog ? width : Math.max(75,width*.48)
    Accessible.role: Accessible.Clock
    Accessible.name: "Elapsed time "+durationText
    function formatDuration(value) { let n=Math.floor(Math.max(0,value));return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].map(v=>String(v).padStart(2,"0")).join(":") }
    function sample() { seconds=backend.workTimer.elapsedSeconds();dial.requestPaint() }
    Component.onCompleted: sample()
    onActiveChanged: if(active)sample()
    onKindChanged: dial.requestPaint()
    Connections { target: backend.workTimer; function onChanged() { face.sample() } }
    Connections { target: Theme; function onDarkChanged() { dial.requestPaint() } }
    Timer { interval: backend.reducedMotion ? 1000 : 33; running: face.animating; repeat: true; triggeredOnStart: true; onTriggered: face.sample() }
    Rectangle {
        anchors.fill: parent; visible: face.kind==="digital"; radius: 9; color: Theme.page; border.color: Theme.line
        Column {
            anchors.centerIn: parent; spacing: 5
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: face.durationText; color: Theme.blue; font.pixelSize: Math.min(32,face.width*.145); font.weight: Font.Medium }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "HH  :  MM  :  SS"; color: Theme.muted; font.pixelSize: 11 }
        }
    }
    Rectangle {
        anchors.fill: parent; visible: face.kind==="flip"; radius: 6; color: "#171b16"; border.color: "#4d5147"
        Row {
            anchors.horizontalCenter: parent.horizontalCenter; y: 10; spacing: 0
            Repeater { model: 6
                Item { required property int index; width: (face.width-46)/6+(index===1 || index===3 ? 12 : 3); height: face.height-34
                    FlipDigit { width: (face.width-46)/6; height: parent.height; value: face.digits.charAt(parent.index); animate: face.running && face.active }
                    Text { visible: parent.index===1 || parent.index===3; anchors.right: parent.right; width: 12; height: parent.height; text: ":"; color: "#eee8d4"; font.pixelSize: face.height*.4; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }
        Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 5; text: "HH  :  MM  :  SS"; color: "#c8c6b8"; font.pixelSize: 11 }
    }
    Canvas {
        id: dial; anchors.fill: parent; visible: face.analog
        onPaint: {
            if(!visible || width<1 || height<1)return
            let c=getContext("2d"),size=Math.min(width,height),r=size/2,cx=width/2,cy=height/2
            c.reset();c.clearRect(0,0,width,height);c.save();c.translate(cx,cy)
            function line(a,inner,outer,color,w) { c.beginPath();c.moveTo(Math.sin(a)*inner,-Math.cos(a)*inner);c.lineTo(Math.sin(a)*outer,-Math.cos(a)*outer);c.strokeStyle=color;c.lineWidth=w;c.lineCap="round";c.stroke() }
            function text(value,x,y,font,color) { c.fillStyle=color;c.font="500 "+font+"px 'IBM Plex Sans'";c.textAlign="center";c.textBaseline="middle";c.fillText(value,x,y) }
            c.beginPath();c.arc(0,0,r-2,0,Math.PI*2);c.fillStyle=Theme.surface;c.fill();c.strokeStyle=Theme.line;c.lineWidth=1;c.stroke()
            let station=face.kind==="station"
            for(let n=0;n<60;n++)line(n*Math.PI/30,r*(n%5===0?.81:.87),r*.93,n%5===0?Theme.muted:Theme.line,station?(n%5===0?2.6:1):1)
            for(let n=0;n<12;n++) { let a=n*Math.PI/6; text(n===0 ? "60" : String(n*5),Math.sin(a)*r*.70,-Math.cos(a)*r*.70,Math.max(10,r*.125),Theme.muted) }
            let elapsed=backend.reducedMotion ? Math.floor(face.seconds) : face.seconds
            function subdial(x,value,total,label) {
                c.save();c.translate(x,r*.12);let sr=r*.235
                c.beginPath();c.arc(0,0,sr,0,Math.PI*2);c.fillStyle=Theme.page;c.fill();c.strokeStyle=Theme.line;c.stroke()
                for(let n=0;n<12;n++)line(n*Math.PI/6,sr*.78,sr*.92,Theme.muted,1)
                line(value/total*Math.PI*2,-sr*.12,sr*.7,Theme.blue,1.7)
                text(label,0,-sr-8,10,Theme.muted);c.restore()
            }
            subdial(-r*.32,elapsed/60%60,60,"MIN")
            subdial(r*.32,elapsed/3600%24,24,"HRS")
            text(face.durationText,0,r*.52,Math.max(10,r*.135),Theme.ink)
            line((elapsed%60)*Math.PI/30,-r*.12,r*.78,station?Theme.blue:"#d54a51",station?2:1.4)
            c.beginPath();c.arc(0,0,3,0,Math.PI*2);c.fillStyle=Theme.blue;c.fill();c.restore()
        }
    }
}
