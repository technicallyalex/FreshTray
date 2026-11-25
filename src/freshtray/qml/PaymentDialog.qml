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
    property string suggestedAmount: ""
    onBalanceChanged: {
        if (amount && !row.id && amount.text === suggestedAmount) {
            suggestedAmount = balance
            amount.text = balance
        }
    }
    function edit(payment) {
        row = payment
        suggestedAmount = payment.amount || balance
        amount.text = suggestedAmount
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
            Caption { Layout.fillWidth: true; text: dialog.state.busy && dialog.state.currentPaymentPending ? "Syncing payment…" : dialog.state.notice || dialog.state.errors.payments || ""; wrapMode: Text.WordWrap; visible: !!text }
            Caption { text: "Payment history"; font.bold: true }
            Repeater {
                model: dialog.visible ? dialog.state.payments : []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: modelData.date + " · " + modelData.method + " · " + modelData.amount + (modelData.note ? "\n" + modelData.note : "") }
                    AppButton { text: "Edit"; visible: modelData.editable; enabled: !dialog.state.busy && !dialog.state.currentPaymentPending; onClicked: dialog.edit(modelData) }
                    AppButton { text: "Remove"; visible: modelData.editable; enabled: !dialog.state.busy && !dialog.state.currentPaymentPending; onClicked: { removal.paymentId = modelData.id; removal.open() } }
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
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Field { id: received; objectName: "paymentReceivedDate"; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD"; Accessible.name: "Received date" }
                        AppButton {
                            objectName: "paymentCalendar"
                            glyph: "calendar"
                            tip: "Choose received date"
                            Accessible.name: "Choose received date"
                            onClicked: { picker.selected = received.text; picker.open() }
                        }
                        DatePicker {
                            id: picker
                            objectName: "paymentDatePicker"
                            parent: Overlay.overlay
                            x: Math.max(8,(parent.width-width)/2)
                            y: Math.max(8,(parent.height-height)/2)
                            onPicked: day => received.text = day
                        }
                    }
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
                        primary: true; enabled: !dialog.state.busy && !dialog.state.currentPaymentPending
                        onClicked: {
                            if (dialog.tools.recordPayment(dialog.row.id || "", {amount:amount.text, date:received.text, method:method.currentText, note:note.text}, false))
                                dialog.edit({})
                        }
                    }
                }
            }
            BillingPending { Layout.fillWidth: true; tools: dialog.tools; currentInvoicePaymentsOnly: true }
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
