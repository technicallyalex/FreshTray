import QtQuick
Item {
    id: digit
    property string value: "0"
    property string previous: value
    property string displayed: ""
    property real progress: 1
    property bool animate: true
    onAnimateChanged: if(!animate) { flip.stop();progress=1;previous=value;displayed=value }
    Component.onCompleted: { displayed=value; previous=value }
    onValueChanged: { if(displayed.length && animate && !backend.reducedMotion) { flip.stop(); previous=displayed; displayed=value; progress=0; flip.start() } else { flip.stop();progress=1;displayed=value;previous=value } }
    NumberAnimation { id: flip; target: digit; property: "progress"; from: 0; to: 1; duration: 360; onFinished: digit.previous=digit.value }
    Rectangle { anchors.fill: parent; color: "#252821"; radius: 3 }
    Text { id: topValue; anchors.fill: parent; text: digit.value; color: "#f1ebd8"; font.family: "IBM Plex Sans"; font.pixelSize: parent.height*.76; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    Item { y: parent.height/2; width: parent.width; height: parent.height/2; clip: true; visible: digit.progress<.5
        Rectangle { anchors.fill: parent; color: "#252821" }
        Text { y: -digit.height/2; width: digit.width; height: digit.height; text: digit.previous; color: "#f1ebd8"; font.pixelSize: digit.height*.76; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }
    Item {
        width: parent.width; height: parent.height/2; clip: true; visible: digit.progress<.5
        transform: Rotation { origin.x: digit.width/2; origin.y: digit.height/2; axis.x: 1; axis.y: 0; axis.z: 0; angle: digit.progress*180 }
        Rectangle { anchors.fill: parent; color: "#30332c" }
        Text { width: digit.width; height: digit.height; text: digit.previous; color: "#f1ebd8"; font.pixelSize: digit.height*.76; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }
    Item {
        y: parent.height/2; width: parent.width; height: parent.height/2; clip: true; visible: digit.progress>=.5 && digit.progress<1
        transform: Rotation { origin.x: digit.width/2; origin.y: 0; axis.x: 1; axis.y: 0; axis.z: 0; angle: -180*(1-digit.progress) }
        Rectangle { anchors.fill: parent; color: "#252821" }
        Text { y: -digit.height/2; width: digit.width; height: digit.height; text: digit.value; color: "#f1ebd8"; font.pixelSize: digit.height*.76; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }
    Rectangle { y: parent.height/2; width: parent.width; height: 1; color: "#0d100c" }
}
