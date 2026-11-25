import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "paymentHistory"
    required property var tools
    required property var invoice
    property var state: tools.state
    property var row: ({})
    property string balance: String(invoice.totals.balance || "0.00")
    function edit(payment) {
        row = payment
        amount.text = payment.amount || balance
        received.text = payment.date || state.date
        method.currentIndex = Math.max(0, state.methods.indexOf(payment.method || "Cash"))
        note.text = payment.note || ""
    }
    title: "Invoice payments"
    parent: Overlay.overlay
    modal: true
    x: (parent.width-width)/2; y: (parent.height-height)/2
    width: Math.min(680,parent.width-28); height: Math.min(590,parent.height-28)
    background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 8 }
    onOpened: { edit({}); tools.preparePayments() }
    contentItem: ScrollView {
        id: scroll
        clip: true; contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 9
            Text { Layout.fillWidth: true; text: "Paid " + dialog.invoice.totals.paid + "  ·  Balance " + dialog.balance + " " + dialog.invoice.draft.currency; color: Theme.ink; font.bold: true }
            Caption { Layout.fillWidth: true; text: dialog.state.errors.payments || dialog.state.notice || ""; wrapMode: Text.WordWrap; visible: !!text }
            Caption { text: "Payment history"; font.bold: true }
            Repeater {
                model: dialog.visible ? dialog.state.payments : []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: modelData.date + " · " + modelData.method + " · " + modelData.amount + (modelData.note ? "\n" + modelData.note : "") }
                    AppButton { text: "Edit"; visible: modelData.editable; enabled: !dialog.state.busy; onClicked: dialog.edit(modelData) }
                    AppButton { text: "Remove"; visible: modelData.editable; enabled: !dialog.state.busy; onClicked: { removal.paymentId = modelData.id; removal.open() } }
                }
            }
            Caption { visible: !dialog.state.payments.length; text: "No payment records available." }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }
            ColumnLayout {
                visible: dialog.state.canPay && (Number(dialog.balance) > 0 || !!dialog.row.id)
                Layout.fillWidth: true
                Caption { text: dialog.row.id ? "Edit manual payment" : "Record a payment received"; font.bold: true }
                GridLayout {
                    Layout.fillWidth: true; columns: 2
                    Caption { text: "Amount" }
                    Field { id: amount; objectName: "paymentAmount"; Layout.fillWidth: true }
                    Caption { text: "Received date" }
                    Field { id: received; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD" }
                    Caption { text: "Method" }
                    Select { id: method; Layout.fillWidth: true; model: dialog.state.methods }
                    Caption { text: "Note / reference" }
                    Field { id: note; Layout.fillWidth: true }
                }
                RowLayout {
                    AppButton { visible: !!dialog.row.id; text: "Cancel edit"; onClicked: dialog.edit({}) }
                    AppButton {
                        objectName: "savePayment"
                        text: dialog.row.id ? "Save correction" : "Record payment"
                        primary: true; enabled: !dialog.state.busy
                        onClicked: {
                            dialog.tools.recordPayment(dialog.row.id || "", {amount:amount.text, date:received.text, method:method.currentText, note:note.text}, false)
                            if (["Payment history updated.", "Saved locally. Sync pending changes when ready."].includes(dialog.tools.state.notice))
                                dialog.edit({})
                        }
                    }
                }
            }
            BillingPending { Layout.fillWidth: true; tools: dialog.tools }
        }
    }
    footer: RowLayout {
        Item { Layout.fillWidth: true }
        AppButton { text: "Close"; onClicked: dialog.close() }
    }
    Dialog {
        id: removal
        parent: Overlay.overlay
        x: (parent.width-width)/2; y: (parent.height-height)/2
        modal: true
        property string paymentId: ""
        title: "Remove this payment?"
        standardButtons: Dialog.Cancel | Dialog.Ok
        onAccepted: { dialog.tools.recordPayment(paymentId, {}, true); dialog.edit({}) }
    }
}
