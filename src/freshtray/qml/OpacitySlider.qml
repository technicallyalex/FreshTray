import QtQuick
import QtQuick.Controls
Slider {
    id: slider
    from: .4; to: 1; stepSize: .05
    leftPadding: 7; rightPadding: 7; topPadding: 8; bottomPadding: 8
    implicitHeight: 32
    background: Rectangle {
        x: slider.leftPadding; y: (slider.height-height)/2
        width: slider.availableWidth; height: 4; radius: 2; color: Theme.line
        Rectangle { width: slider.visualPosition*parent.width; height: parent.height; radius: 2; color: Theme.blue }
    }
    handle: Rectangle {
        x: slider.leftPadding+slider.visualPosition*(slider.availableWidth-width)
        y: (slider.height-height)/2
        width: 14; height: 14; radius: 7; color: Theme.blue
        border.color: slider.activeFocus ? Theme.ink : Theme.blue
        border.width: slider.activeFocus ? 2 : 0
    }
}
