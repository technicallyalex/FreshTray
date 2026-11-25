import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var tools
    property var state: tools.state
    property bool currentInvoicePaymentsOnly: false
    property var pending: currentInvoicePaymentsOnly ? state.pending.filter(row => row.kind === "payments" && row.invoiceId === state.paymentInvoiceId) : state.pending
    visible: !state.local && pending.length > 0
    spacing: 6
    RowLayout {
        Layout.fillWidth: true
        Caption { Layout.fillWidth: true; text: "Pending FreshBooks changes" }
        AppButton {
            objectName: "syncBillingChanges"
            text: "Sync pending changes"
            visible: root.pending.some(row => !row.automatic && row.status === "queued")
            enabled: !root.state.busy
            onClicked: {
                if (root.currentInvoicePaymentsOnly)
                    root.tools.confirmLegacyPaymentSync(root.state.paymentInvoiceId)
                else
                    backend.confirmBillingSync()
            }
        }
    }
    Repeater {
        model: root.visible ? root.pending : []
        delegate: RowLayout {
            required property var modelData
            Layout.fillWidth: true
            Caption {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: modelData.label + " · " + (modelData.automatic && modelData.status === "queued" ? "Waiting to sync automatically" : modelData.status) + (modelData.issue ? "\n" + modelData.issue : "")
            }
            AppButton { text: "Remove pending change"; enabled: !root.state.busy; onClicked: root.tools.discard(modelData.id) }
        }
    }
}
