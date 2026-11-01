import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "updateDialog"
    property var update: backend.updater.state
    modal: true
    width: Math.min(520,parent.width-32)
    height: Math.min(480,parent.height-32)
    x: (parent.width-width)/2; y: (parent.height-height)/2
    closePolicy: update.phase==="preparing" ? Popup.NoAutoClose : Popup.CloseOnEscape
    header: Text {
        text: dialog.update.version ? "FreshTray " + dialog.update.version : "FreshTray updates"
        color: Theme.ink; font.pixelSize: 18; font.bold: true; padding: 16
    }
    background: Rectangle { color: Theme.surface; radius: 10; border.color: Theme.line }
    contentItem: ColumnLayout {
        spacing: 12
        Text { objectName: "updateStatus"; Layout.fillWidth: true; text: dialog.update.message; wrapMode: Text.WordWrap; color: Theme.ink; font.pixelSize: 13 }
        ProgressBar {
            objectName: "updateProgress"; Layout.fillWidth: true
            visible: dialog.update.phase==="downloading" || dialog.update.phase==="checking" || dialog.update.phase==="preparing"
            indeterminate: dialog.update.phase!=="downloading"; from: 0; to: 100; value: dialog.update.progress
        }
        ScrollView {
            objectName: "updateNotesScroll"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            TextArea {
                objectName: "updateNotes"; readOnly: true; selectByMouse: true
                textFormat: TextEdit.PlainText
                text: dialog.update.notes || "Release notes will appear here when an update is available."
                wrapMode: TextEdit.Wrap; color: Theme.ink; font.pixelSize: 13
                background: Rectangle { color: Theme.page; border.color: Theme.line; radius: 6 }
            }
        }
        Text {
            Layout.fillWidth: true; text: dialog.update.portable ? "The app restarts after installation. Your account data stays on this PC." : "Automatic installation is available in the portable executable."
            wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11
        }
    }
    footer: Item {
        implicitHeight: 56
        RowLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            AppButton {
                objectName: "dismissUpdate"
                text: dialog.update.phase==="downloading" ? "Cancel download" : "Dismiss"
                enabled: dialog.update.phase!=="preparing"
                onClicked: { backend.updater.dismiss(); dialog.close() }
            }
            Item { Layout.fillWidth: true }
            AppButton {
                objectName: "downloadUpdate"; text: "Download update"; primary: true
                visible: dialog.update.phase==="available" || (dialog.update.phase==="error" && dialog.update.version.length>0)
                enabled: dialog.update.portable
                onClicked: backend.updater.downloadUpdate()
            }
            AppButton {
                objectName: "installUpdate"; text: "Install and restart"; primary: true
                visible: dialog.update.phase==="ready"; enabled: dialog.update.portable
                onClicked: backend.updater.installUpdate()
            }
            AppButton {
                text: "Check again"; visible: dialog.update.phase==="current" || dialog.update.phase==="error"
                onClicked: backend.updater.checkUpdates()
            }
        }
    }
    onRejected: backend.updater.dismiss()
}
