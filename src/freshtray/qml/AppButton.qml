import QtQuick
import QtQuick.Controls
Button {
    id: control
    property bool primary: false
    property bool destructive: false
    property bool quiet: false
    property bool selected: false
    property string glyph: ""
    property string tip: ""
    implicitHeight: Theme.compact ? 30 : 34
    implicitWidth: glyph && !text ? 34 : Math.max(64, label.implicitWidth+28+(glyph ? 25 : 0))
    padding: 8
    opacity: enabled ? 1 : .45
    font.pixelSize: 13
    Accessible.name: tip || text
    ToolTip.visible: hovered && tip.length>0
    ToolTip.text: tip
    contentItem: Row {
        spacing: 7
        anchors.centerIn: parent
        Icon { visible: control.glyph.length>0; name: control.glyph; ink: (control.primary || control.destructive) ? "white" : Theme.ink; anchors.verticalCenter: parent.verticalCenter }
        Text { id: label; text: control.text; color: (control.primary || control.destructive) ? "white" : control.selected ? Theme.blue : Theme.ink; font: control.font; anchors.verticalCenter: parent.verticalCenter }
    }
    background: Rectangle {
        radius: 6
        color: control.destructive ? (control.down ? "#871522" : control.hovered ? "#9f1c2c" : "#b42332") : control.selected ? Theme.selected : control.primary ? (control.down ? "#006f00" : control.hovered ? "#009b12" : Theme.green) : control.down ? Theme.selected : control.hovered ? Theme.hover : control.quiet ? "transparent" : Theme.surface
        border.color: control.activeFocus ? Theme.blue : control.primary || control.destructive || control.quiet ? "transparent" : Theme.line
        border.width: control.activeFocus ? 2 : 1
    }
}
