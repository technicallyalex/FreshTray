import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "estimatesPanel"
    required property var tools
    property var state: tools.state
    property var draft: state.estimate
    property bool editing: !!draft.id
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: root.editing ? "Estimate" : "Estimates"; color: Theme.ink; font.pixelSize: 26; font.bold: true }
        AppButton { visible: root.editing; text: "All estimates"; onClicked: root.tools.closeEstimate() }
        AppButton { objectName: "newEstimate"; visible: !root.editing; text: "New estimate"; primary: true; enabled: !root.state.busy; onClicked: root.tools.openEstimate("") }
    }
    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: root.state.notice || root.state.errors.estimates || ""; visible: !!text }
    RowLayout {
        visible: !root.editing
        Layout.fillWidth: true
        Field { id: query; Layout.fillWidth: true; placeholderText: "Search estimates" }
        Select { id: status; model: ["All statuses","Draft","Sent","Viewed","Replied","Accepted","Invoiced"]; Layout.preferredWidth: 120 }
        Select { id: clientFilter; model: [{id:"",name:"All clients"}].concat(root.state.clients); textRole: "name"; valueRole: "id"; Layout.preferredWidth: 140 }
        Check { id: archived; text: "Archived" }
    }
    ListView {
        id: list
        visible: !root.editing
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        model: visible && root.visible ? root.state.estimates.filter(row => row.archived === archived.checked &&
                (status.currentIndex <= 0 || row.status === status.currentText) &&
                (!clientFilter.currentValue || row.client === String(clientFilter.currentValue)) &&
                (row.name + " " + row.number).toLowerCase().includes(query.text.toLowerCase())) : []
        delegate: ColumnLayout {
            width: list.width
            required property var modelData
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; textFormat: Text.PlainText; color: Theme.ink; font.bold: true; text: modelData.number + " · " + modelData.name; elide: Text.ElideRight }
                    Caption { text: modelData.date + " · " + modelData.status }
                }
                Caption { text: modelData.total + " " + modelData.currency }
                AppButton { text: "Open"; enabled: !root.state.busy; onClicked: root.tools.openEstimate(modelData.id) }
            }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }
        }
        Caption { anchors.centerIn: parent; visible: list.count === 0; text: "No estimates match this view" }
        ScrollBar.vertical: ScrollBar {}
    }
    Loader {
        Layout.fillWidth: true
        Layout.fillHeight: true
        active: root.visible && root.editing
        sourceComponent: Component {
            ScrollView {
                id: editor
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: editor.availableWidth
                    spacing: 12
                    Flow {
                        Layout.fillWidth: true; spacing: 7
                        AppButton { objectName: "saveEstimate"; text: "Save"; primary: true; enabled: !root.state.busy; onClicked: root.tools.estimateAction("save") }
                        AppButton { text: "Preview"; onClicked: root.tools.estimateAction("preview") }
                        AppButton { text: "Export PDF"; onClicked: root.tools.estimateAction("pdf") }
                        AppButton { text: "Email draft"; onClicked: root.tools.estimateAction("email") }
                        AppButton { text: "Duplicate"; enabled: !root.state.busy; onClicked: root.tools.estimateAction("duplicate") }
                        AppButton { text: root.draft.archived ? "Restore" : "Archive"; enabled: !root.state.busy; onClicked: root.tools.estimateAction(root.draft.archived ? "restore" : "archive") }
                        AppButton { visible: !root.state.local; text: "Queue for FreshBooks"; enabled: !root.state.busy; onClicked: root.tools.estimateAction("sync") }
                        AppButton { visible: !root.state.local && !!root.draft.remote_id; text: "Send or manage in FreshBooks"; onClicked: root.tools.estimateAction("web") }
                        AppButton { visible: root.state.local && root.draft.status === "Draft"; text: "Mark as sent"; onClicked: root.tools.estimateAction("sent") }
                        AppButton { visible: root.state.local && ["Draft","Sent"].includes(root.draft.status); text: "Mark as accepted"; onClicked: root.tools.estimateAction("accepted") }
                        AppButton { objectName: "convertEstimate"; text: "Convert to invoice"; enabled: !root.state.busy; onClicked: root.tools.estimateAction("convert") }
                    }
                    Caption { Layout.fillWidth: true; text: (root.draft.status || "") + (root.draft.archived ? " · Archived" : "") }
                    Loader {
                        Layout.fillWidth: true
                        active: !!root.state.preview
                        sourceComponent: Rectangle {
                            implicitHeight: sheet.implicitHeight + 36
                            radius: 8
                            color: "#ffffff"
                            border.color: Theme.line
                            Text {
                                id: sheet
                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                                anchors.margins: 18
                                color: "#142d47"
                                textFormat: Text.RichText
                                text: root.state.preview
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Caption { text: "Client" }
                        Select {
                            Layout.fillWidth: true
                            model: [{id:"", name:"Choose a client"}].concat(root.state.clients.filter(c => !c.archived || String(c.id) === root.draft.client))
                            textRole: "name"
                            currentIndex: model.findIndex(c => String(c.id) === root.draft.client)
                            onActivated: index => root.tools.estimateField("client",String(model[index].id))
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: editor.availableWidth > 760 ? 4 : 2
                        Repeater {
                            model: [{key:"number",label:"Estimate number"},{key:"date",label:"Issue date (YYYY-MM-DD)"},
                                    {key:"currency",label:"Currency"},{key:"po",label:"Reference"},{key:"discount",label:"Discount (%)"}]
                            ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                Caption { text: modelData.label }
                                Field { Layout.fillWidth: true; objectName: "estimate_" + modelData.key; text: root.draft[modelData.key] || ""; onEditingFinished: root.tools.estimateField(modelData.key,text) }
                            }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }
                    Flow {
                        Layout.fillWidth: true; spacing: 7
                        Select {
                            width: 260; model: [{name:"Choose a saved item",id:""}].concat(root.state.items); textRole: "name"
                            onActivated: index => { if (index > 0) root.tools.editEstimateLines(String(model[index].id),-1); currentIndex = 0 }
                        }
                        AppButton { text: "Add line"; onClicked: root.tools.editEstimateLines("",-1) }
                    }
                    Repeater {
                        model: root.draft.lines ? root.draft.lines.length : 0
                        delegate: ColumnLayout {
                            id: line
                            required property int index
                            property var row: (root.draft.lines || [])[index] || ({})
                            Layout.fillWidth: true
                            RowLayout {
                                Layout.fillWidth: true
                                Field { Layout.fillWidth: true; placeholderText: "Item or service"; objectName: "estimateLineName" + line.index; text: line.row.name || ""; onEditingFinished: root.tools.estimateLine(line.index,"name",text) }
                                AppButton { text: "Remove line"; enabled: root.draft.lines && root.draft.lines.length > 1; onClicked: root.tools.editEstimateLines("",line.index) }
                            }
                            Field { Layout.fillWidth: true; placeholderText: "Description"; text: line.row.description || ""; onEditingFinished: root.tools.estimateLine(line.index,"description",text) }
                            GridLayout {
                                Layout.fillWidth: true; columns: editor.availableWidth > 760 ? 4 : 2
                                Repeater {
                                    model: [{key:"qty",label:"Qty"},{key:"rate",label:"Rate"},{key:"tax",label:"Tax (%)"},{key:"tax2",label:"Second tax (%)"}]
                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Caption { text: modelData.label }
                                        Field { Layout.fillWidth: true; objectName: "estimateLine_" + modelData.key + line.index; text: line.row[modelData.key] || ""; onEditingFinished: root.tools.estimateLine(line.index,modelData.key,text) }
                                    }
                                }
                            }
                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }
                        }
                    }
                    Caption { Layout.alignment: Qt.AlignRight; text: "Subtotal " + (root.state.totals.subtotal || "—") + "   ·   Tax " + (root.state.totals.tax || "—") }
                    Text { Layout.alignment: Qt.AlignRight; text: "Total " + (root.state.totals.total || "—") + " " + (root.draft.currency || ""); color: Theme.ink; font.pixelSize: 20; font.bold: true }
                    Repeater {
                        model: [{key:"note",label:"Notes"},{key:"terms",label:"Terms"}]
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Caption { text: modelData.label }
                            TextArea {
                                Layout.fillWidth: true; Layout.preferredHeight: 74
                                color: Theme.ink; textFormat: TextEdit.PlainText; wrapMode: TextEdit.Wrap
                                background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 5 }
                                text: root.draft[modelData.key] || ""
                                onEditingFinished: root.tools.estimateField(modelData.key,text)
                            }
                        }
                    }
                }
            }
        }
    }
    BillingPending { Layout.fillWidth: true; tools: root.tools }
}
