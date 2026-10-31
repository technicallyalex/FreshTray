import QtQuick
import QtQuick.Controls
ComboBox {
    id: control
    implicitHeight: Theme.compact ? 30 : 34
    implicitWidth: 140
    font.pixelSize: 13
    leftPadding: 10; rightPadding: 28
    contentItem: Text { text: control.displayText; color: control.enabled ? Theme.ink : Theme.muted; font: control.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
    indicator: Icon { name: "down"; width: 16; height: 16; ink: Theme.muted; x: control.width-23; y: (control.height-height)/2 }
    background: Rectangle { radius: 5; color: Theme.surface; border.color: control.activeFocus ? Theme.blue : Theme.line; border.width: control.activeFocus ? 2 : 1 }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width; height: 32
        contentItem: Text { text: control.textRole ? modelData[control.textRole] : modelData; color: Theme.ink; font: control.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 4; color: parent.highlighted ? Theme.selected : Theme.surface }
        highlighted: control.highlightedIndex === index
    }
    popup: Popup {
        y: control.height+4; width: control.width
        padding: 5
        implicitHeight: Math.min(300, contentItem.implicitHeight+10)
        background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 7 }
        contentItem: ListView { clip: true; implicitHeight: contentHeight; model: control.popup.visible ? control.delegateModel : null; currentIndex: control.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
    }
}
