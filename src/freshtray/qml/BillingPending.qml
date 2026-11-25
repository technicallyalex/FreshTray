import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var tools
    property var state: tools.state
    visible: !state.local && state.pending.length > 0
    spacing: 6
    RowLayout {
        Layout.fillWidth: true
        Caption { Layout.fillWidth: true; text: "Pending FreshBooks changes" }
        AppButton {
            objectName: "syncBillingChanges"
            text: "Sync pending changes"
            enabled: !root.state.busy && root.state.pending.some(row => row.status === "queued")
            onClicked: backend.confirmBillingSync()
        }
    }
    Repeater {
        model: root.visible ? root.state.pending : []
        delegate: RowLayout {
            required property var modelData
            Layout.fillWidth: true
            Caption {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: modelData.label + " · " + modelData.status + (modelData.issue ? "\n" + modelData.issue : "")
            }
            AppButton { text: "Remove pending change"; enabled: !root.state.busy; onClicked: root.tools.discard(modelData.id) }
        }
    }
}
