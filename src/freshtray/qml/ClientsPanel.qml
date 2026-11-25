import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "clientsPanel"
    required property var tools
    property var state: tools.state
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "Clients"; color: Theme.ink; font.pixelSize: 26; font.bold: true }
        AppButton { objectName: "addClient"; text: "Add client"; primary: true; enabled: !root.state.busy; onClicked: editor.edit({}) }
    }
    RowLayout {
        Layout.fillWidth: true
        Field { id: search; Layout.fillWidth: true; placeholderText: "Search clients" }
        Select { id: order; model: ["Name A–Z", "Name Z–A"]; Layout.preferredWidth: 120 }
        Check { id: archived; text: "Archived" }
    }
    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; visible: !!text; text: root.state.notice || root.state.errors.clients || "" }
    ListView {
        id: list
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: root.visible ? root.state.clients.filter(row => !!row.archived === archived.checked &&
            [row.name, row.email, row.phone, row.company].join(" ").toLowerCase().includes(search.text.toLowerCase()))
            .sort((a,b) => order.currentIndex === 0 ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)) : []
        delegate: ColumnLayout {
            required property var modelData
            width: list.width
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; textFormat: Text.PlainText; text: modelData.name; color: Theme.ink; elide: Text.ElideRight; font.bold: true }
                    Caption { Layout.fillWidth: true; text: modelData.email || modelData.phone || ""; elide: Text.ElideRight; visible: !!text }
                }
                AppButton { text: "Edit"; enabled: !root.state.busy; onClicked: editor.edit(modelData) }
                AppButton { text: modelData.archived ? "Restore" : "Archive"; enabled: !root.state.busy; onClicked: root.tools.archiveClient(String(modelData.id), !modelData.archived) }
            }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }
        }
        Caption { anchors.centerIn: parent; visible: list.count === 0; text: archived.checked ? "No archived clients" : "No clients match this view" }
        ScrollBar.vertical: ScrollBar {}
    }
    BillingPending { Layout.fillWidth: true; tools: root.tools }
    Dialog {
        id: editor
        objectName: "clientEditor"
        parent: Overlay.overlay
        modal: true
        title: clientId ? "Edit client" : "Add client"
        property string clientId: ""
        property var initial: ({})
        property var values: ({})
        function edit(row) {
            clientId = row.id === undefined ? "" : String(row.id)
            initial = row
            values = Object.assign({}, row)
            if (!row.company && !row.first && !row.last && row.name)
                values.company = row.name
            open()
        }
        x: (parent.width - width) / 2; y: (parent.height - height) / 2
        width: Math.min(580, parent.width - 32); height: Math.min(610, parent.height - 32)
        background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 8 }
        contentItem: ScrollView {
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 7
                Repeater {
                    model: editor.visible ? [{key:"company", label:"Company"}, {key:"first",label:"First name"},
                        {key:"last",label:"Last name"}, {key:"email",label:"Email"}, {key:"phone",label:"Phone"},
                        {key:"street",label:"Street address"}, {key:"street2",label:"Address line 2"},
                        {key:"city",label:"City"}, {key:"region",label:"State / region"},
                        {key:"postal",label:"Postal code"}, {key:"country",label:"Country"}] : []
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Caption { text: modelData.label }
                        Field { Layout.fillWidth: true; objectName: "client_" + modelData.key; text: editor.values[modelData.key] || ""; onTextEdited: { editor.values[modelData.key] = text; if (["street","street2","city","region","postal","country"].includes(modelData.key)) editor.values.address = "" } }
                    }
                }
                Caption { Layout.fillWidth: true; text: root.state.notice; wrapMode: Text.WordWrap }
            }
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            AppButton { text: "Cancel"; onClicked: editor.close() }
            AppButton {
                objectName: "saveClient"
                text: "Save client"; primary: true
                onClicked: {
                    root.tools.saveClient(editor.clientId, editor.values)
                    if (["Client saved.", "Saved locally. Sync pending changes when ready."].includes(root.tools.state.notice))
                        editor.close()
                }
            }
        }
    }
}
