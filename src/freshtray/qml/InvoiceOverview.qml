import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var state
    property var billing
    implicitHeight: overviewContent.implicitHeight
    function statusColor(status) { return status.toLowerCase()==="paid" ? (Theme.dark ? "#285941" : "#b9dfbd") : status==="Overdue" ? (Theme.dark ? "#713443" : "#ffc8d1") : (Theme.dark ? "#294660" : "#e6f1fc") }
    ColumnLayout {
        id: overviewContent; width: parent.width; spacing: 18
    Repeater {
        model: root.state.summaries
        delegate: ColumnLayout {
            required property var modelData
            Layout.fillWidth: true; spacing: 10
            Caption { text: modelData.currency }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                Repeater {
                    model: [{value:modelData.overdue,label:"overdue"},{value:modelData.outstanding,label:"total outstanding"},{value:modelData.draft,label:"in draft"}]
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 6
                        Text { Layout.fillWidth: true; text: modelData.value; color: Theme.blue; font.bold: true; font.pixelSize: root.width<650 ? 23 : 32; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
                        Caption { Layout.fillWidth: true; text: modelData.label; horizontalAlignment: Text.AlignHCenter }
                    }
                }
            }
        }
    }
    Text { text: "Recently updated"; color: Theme.ink; font.bold: true; font.pixelSize: 18; visible: root.state.recent.length>0 }
    GridLayout {
        Layout.fillWidth: true; columns: root.width<650 ? 2 : 4; columnSpacing: 12; rowSpacing: 12
        Repeater {
            model: root.state.recent
            delegate: Rectangle {
                required property var modelData
                Layout.preferredWidth: (root.width-((root.width<650 ? 2 : 4)-1)*12)/(root.width<650 ? 2 : 4); Layout.minimumWidth: 0; implicitHeight: 155
                radius: 6; color: Theme.surface; border.color: Theme.line; border.width: 2
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 12; spacing: 4
                    Caption { Layout.fillWidth: true; text: modelData.number; elide: Text.ElideRight }
                    Text { Layout.fillWidth: true; text: modelData.client; textFormat: Text.PlainText; color: Theme.ink; font.bold: true; elide: Text.ElideRight }
                    Caption { text: modelData.date }
                    Item { Layout.fillHeight: true }
                    Text { Layout.fillWidth: true; text: modelData.total+" "+modelData.currency; color: Theme.ink; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 26; radius: 3; color: root.statusColor(modelData.status)
                        Text { anchors.centerIn: parent; text: modelData.status; color: Theme.ink; font.pixelSize: 12 }
                    }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !root.state.busy; onClicked: root.billing.openInvoice(modelData.id) }
                Accessible.role: Accessible.Button; Accessible.name: "Open invoice "+modelData.number; Accessible.onPressAction: root.billing.openInvoice(modelData.id)
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Text { text: "All invoices"; color: Theme.ink; font.bold: true; font.pixelSize: 19 }
        Item { Layout.fillWidth: true }
        AppButton { objectName: "newInvoice"; text: "New invoice"; primary: true; enabled: !root.state.busy; onClicked: root.billing.newInvoice() }
    }
    RowLayout {
        Layout.fillWidth: true
        Field { id: search; objectName: "invoiceSearch"; Layout.fillWidth: true; Layout.minimumWidth: 0; placeholderText: "Search invoices"; onTextEdited: root.billing.filterRows(text,status.currentText) }
        Select { id: status; Layout.preferredWidth: 115; model: ["All","Draft","Sent","Overdue","Paid"]; onActivated: root.billing.filterRows(search.text,currentText) }
        Select { Layout.preferredWidth: Math.min(180,root.width*.29); model: [{id:"",name:"All clients"}].concat(root.state.clients); textRole: "name"; onActivated: root.billing.filterClient(String(model[currentIndex].id)) }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 14
        Caption { Layout.preferredWidth: root.width*.25; text: "Client / Invoice number" }
        Caption { Layout.preferredWidth: Math.max(20,root.width*.75-258); Layout.minimumWidth: 0; text: "Description" }
        Caption { Layout.preferredWidth: 96; text: "Issued / Due" }
        Caption { Layout.preferredWidth: 120; text: "Amount / Status"; horizontalAlignment: Text.AlignRight }
    }
    ListView {
        id: invoiceList; objectName: "invoiceList"
        Layout.fillWidth: true; Layout.preferredHeight: Math.min(450,contentHeight)
        clip: true; reuseItems: true; model: root.state.rows
        ScrollBar.vertical: ScrollBar { }
            delegate: Item {
                required property var modelData
                width: ListView.view ? ListView.view.width : 0; height: modelData.issue ? 98 : 74; clip: true
                Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }
                RowLayout {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: 12; spacing: 14
                    ColumnLayout { Layout.preferredWidth: root.width*.25; Layout.minimumWidth: 0; spacing: 3
                        Text { Layout.fillWidth: true; text: modelData.client; textFormat: Text.PlainText; color: Theme.ink; elide: Text.ElideRight }
                        Caption { Layout.fillWidth: true; text: modelData.number; elide: Text.ElideRight }
                    }
                    Text { Layout.preferredWidth: Math.max(20,root.width*.75-258); Layout.minimumWidth: 0; maximumLineCount: 1; wrapMode: Text.NoWrap; clip: true; text: modelData.description.replace(/[\r\n]+/g," "); textFormat: Text.PlainText; color: Theme.ink; elide: Text.ElideRight }
                    ColumnLayout { Layout.preferredWidth: 96; spacing: 3; Caption { text: modelData.date; color: Theme.ink } Caption { text: modelData.due } }
                    ColumnLayout { Layout.preferredWidth: 120; spacing: 3
                        Text { Layout.fillWidth: true; text: modelData.total+" "+modelData.currency; color: Theme.ink; horizontalAlignment: Text.AlignRight; font.pixelSize: 13; elide: Text.ElideRight }
                        Rectangle { Layout.alignment: Qt.AlignRight; implicitWidth: badge.implicitWidth+16; implicitHeight: 23; radius: 4; color: root.statusColor(modelData.status); Text { id: badge; anchors.centerIn: parent; text: modelData.status; color: Theme.ink; font.pixelSize: 12 } }
                    }
                }
                Caption { anchors.bottom: parent.bottom; anchors.bottomMargin: 5; width: parent.width; visible: !!modelData.issue; text: modelData.issue; elide: Text.ElideRight }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !root.state.busy; onClicked: root.billing.openInvoice(modelData.id) }
                Accessible.role: Accessible.Button; Accessible.name: "Open invoice "+modelData.number; Accessible.onPressAction: root.billing.openInvoice(modelData.id)
            }
    }
    Caption { Layout.fillWidth: true; visible: !root.state.rows.length; wrapMode: Text.WordWrap; text: root.state.clients.length ? "No invoices match this view." : "Add your business and first client using Business & local records to get started." }
    AppButton { text: "Resume unsaved draft"; enabled: !root.state.busy; onClicked: root.billing.resume() }
}
}
