import QtQuick
Rectangle {
    id: cover
    objectName: "loadingSkeleton"
    property bool active: false
    property bool shown: false
    color: Theme.surface
    radius: 8
    visible: shown
    onActiveChanged: { if(active) delay.restart(); else { delay.stop(); shown=false } }
    Timer { id: delay; interval: 140; onTriggered: cover.shown=cover.active }
    Column {
        anchors.fill: parent; anchors.margins: 18; spacing: 15
        Repeater {
            model: Math.max(1,Math.floor((cover.height-36)/47))
            Rectangle { required property int index; width: index%3===0 ? (cover.width-36)*.6 : cover.width-36; height: 30; radius: 6; color: Theme.skeleton
                SequentialAnimation on opacity { running: cover.visible; loops: Animation.Infinite; NumberAnimation { to: .45; duration: 700 } NumberAnimation { to: 1; duration: 700 } }
            }
        }
    }
    MouseArea { anchors.fill: parent }
}
