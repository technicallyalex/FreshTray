import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: form
    required property string scope
    property var formData: scope==="log" ? backend.state.log : backend.state.monthForm
    property bool compact: false
    property bool ready: backend.state.catalogReady && (scope!=="month" || backend.state.monthReady)
    property bool canEdit: ready && !backend.state.busy && (scope!=="month" || backend.state.selected<=Qt.formatDate(new Date(),"yyyy-MM-dd"))
    spacing: Theme.compact ? 5 : compact ? 7 : 11
    function indexFor(items,value) { for(let i=0;i<items.length;i++) if(items[i].value===value) return i; return -1 }
    function put(key,value) { backend.setField(scope,key,value) }
    Text { text: form.formData.editing ? "Edit time entry" : form.compact ? "Add time" : "Client & work"; color: Theme.ink; font.pixelSize: form.compact ? 18 : 15; font.bold: true }
    Text { Layout.fillWidth: true; visible: form.formData.billed; text: "Already billed. Billing status is retained. Review the related invoice after editing."; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
    ColumnLayout {
        Layout.fillWidth: true; spacing: 4
        Caption { text: "Client" }
        Select { objectName: form.scope+"Client"; Layout.fillWidth: true; enabled: form.canEdit; model: backend.state.clients; textRole: "name"; currentIndex: form.indexFor(model,form.formData.client); onActivated: form.put("client",model[currentIndex].value) }
    }
    GridLayout {
        Layout.fillWidth: true; columns: 2; columnSpacing: 10; rowSpacing: 4
        Caption { text: "Project · optional" }
        Caption { text: "Service · optional" }
        Select { Layout.fillWidth: true; Layout.preferredWidth: 1; enabled: form.canEdit; model: form.formData.projects; textRole: "name"; currentIndex: form.indexFor(model,form.formData.project); onActivated: form.put("project",model[currentIndex].value) }
        Select { Layout.fillWidth: true; Layout.preferredWidth: 1; enabled: form.canEdit; model: form.formData.services; textRole: "name"; currentIndex: form.indexFor(model,form.formData.service); onActivated: form.put("service",model[currentIndex].value) }
        Caption { text: "Date"; Layout.topMargin: Theme.compact ? 0 : form.compact ? 2 : 8 }
        Caption { text: "Hours · H:MM or decimal"; Layout.topMargin: Theme.compact ? 0 : form.compact ? 2 : 8 }
        RowLayout {
            Layout.fillWidth: true; spacing: 5
            Field { objectName: form.scope+"Date"; Layout.fillWidth: true; Layout.minimumWidth: 90; text: form.formData.day; enabled: form.canEdit; Accessible.name: "Entry date"; onTextEdited: form.put("day",text) }
            AppButton { glyph: "calendar"; tip: "Choose entry date"; enabled: form.canEdit; onClicked: { datePicker.selected=form.formData.day; datePicker.open() } }
            DatePicker { id: datePicker; objectName: form.scope+"Picker"; parent: Overlay.overlay; x: Math.max(8,(parent.width-width)/2); y: Math.max(8,(parent.height-height)/2); onPicked: function(day) { form.put("day",day) } }
        }
        Field { objectName: form.scope+"Hours"; Layout.fillWidth: true; Layout.preferredWidth: 1; enabled: form.canEdit; text: form.formData.hours; Accessible.name: "Hours"; onTextEdited: form.put("hours",text) }
    }
    ColumnLayout {
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 4
        Caption { text: "What did you work on?" }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.minimumHeight: Theme.compact ? 40 : form.compact ? 58 : 68
            Layout.preferredHeight: form.compact ? 64 : 90
            radius: 5; color: Theme.surface; border.color: note.activeFocus ? Theme.blue : Theme.line; border.width: note.activeFocus ? 2 : 1
            Flickable {
                anchors.fill: parent; anchors.margins: 1; clip: true
                contentWidth: width; contentHeight: note.implicitHeight
                TextArea.flickable: TextArea {
                    id: note; objectName: form.scope+"Note"; text: form.formData.note; enabled: form.canEdit
                    padding: 9; color: Theme.ink; font.pixelSize: 13; wrapMode: TextEdit.Wrap
                    selectByMouse: true; background: null; Accessible.name: "Work note"
                    onTextChanged: if(activeFocus && text!==form.formData.note) form.put("note",text)
                }
            }
        }
    }
    RowLayout {
        objectName: form.scope+"Actions"
        Layout.fillWidth: true; Layout.fillHeight: false
        Layout.minimumHeight: Theme.compact ? 30 : 34
        Layout.topMargin: 4
        spacing: 8
        Check { text: "Billable"; checked: form.formData.billable; enabled: form.canEdit; onToggled: form.put("billable",checked) }
        Item { Layout.fillWidth: true }
        AppButton { visible: form.formData.editing; text: "Cancel"; quiet: true; enabled: form.canEdit; onClicked: backend.clearForm(form.scope) }
        AppButton { objectName: form.scope+"Save"; primary: true; text: form.formData.editing ? "Save changes" : "Log time"; glyph: "check"; enabled: form.canEdit; onClicked: backend.submit(form.scope) }
    }
}
