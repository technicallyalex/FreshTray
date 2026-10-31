import QtQuick
import QtQuick.Controls
Pane {
    property bool outlined: true
    property bool fadingOutline: true
    padding: Theme.compact ? 10 : 14
    implicitHeight: (contentChildren.length ? contentChildren[0].implicitHeight : 0)+topPadding+bottomPadding
    background: Rectangle {
        radius: 9; color: Theme.surface
        PanelOutline { anchors.fill: parent; radius: parent.radius; visible: outlined; fading: fadingOutline }
    }
}
