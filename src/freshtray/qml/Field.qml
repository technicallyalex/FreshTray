import QtQuick
import QtQuick.Controls
TextField {
    id: control
    implicitHeight: Theme.compact ? 30 : 34
    padding: 9
    font.pixelSize: 13
    color: Theme.ink
    placeholderTextColor: Theme.muted
    selectByMouse: true
    selectionColor: Theme.blue
    selectedTextColor: "white"
    background: Rectangle { radius: 5; color: Theme.surface; border.color: control.activeFocus ? Theme.blue : Theme.line; border.width: control.activeFocus ? 2 : 1 }
}
