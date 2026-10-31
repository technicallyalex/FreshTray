import QtQuick
import QtQuick.Controls
CheckBox {
    id: control
    implicitHeight: Theme.compact ? 25 : 30
    spacing: 9
    font.pixelSize: 13
    indicator: Rectangle {
        x: 0; y: (control.height-height)/2; width: 18; height: 18; radius: 4
        color: control.checked ? Theme.blue : Theme.surface
        border.color: control.activeFocus ? Theme.blue : control.checked ? Theme.blue : Theme.muted
        Icon { anchors.centerIn: parent; width: 14; height: 14; name: "check"; ink: "white"; visible: control.checked }
    }
    contentItem: Text { text: control.text; color: Theme.ink; font: control.font; leftPadding: 27; verticalAlignment: Text.AlignVCenter; wrapMode: Text.WordWrap }
}
