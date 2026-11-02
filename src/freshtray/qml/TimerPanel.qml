import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: panel
    property var timerData: backend.workTimer.state
    property var form: backend.state.timerForm
    function indexFor(items,value) { for(let i=0;i<items.length;i++)if(items[i].value===value)return i;return -1 }
    spacing: 12
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Timer"; color: Theme.ink; font.pixelSize: 26; font.bold: true }
        Item { Layout.fillWidth: true }
        AppButton { text: panel.timerData.popout ? "Hide pop-out" : "Open pop-out"; onClicked: backend.workTimer.setting("popout",!panel.timerData.popout) }
    }
    GridLayout {
        Layout.fillWidth: true; Layout.fillHeight: true; columns: panel.width<460 ? 1 : 2; columnSpacing: 24; rowSpacing: 14
        ColumnLayout {
            Layout.fillWidth: true; Layout.preferredWidth: 250; Layout.alignment: Qt.AlignTop; spacing: 12
            ClockFace { objectName: "timerMainClock"; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 180; Layout.preferredHeight: analog ? 180 : 95; kind: panel.timerData.face; active: panel.visible }
            TimerControls { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                ColumnLayout { Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 6
                    Caption { text: "Timer face" }
                    AppButton { Layout.fillWidth: true; text: faceTray.names[faceTray.kinds.indexOf(panel.timerData.face)]; onClicked: faceTray.open() }
                }
                ColumnLayout { Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 6
                    Caption { text: "Pop-out opacity" }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 34; radius: 6; color: Theme.surface; border.color: Theme.line
                        OpacitySlider { objectName: "timerOpacity"; anchors.fill: parent; anchors.leftMargin: 3; anchors.rightMargin: 3; value: panel.timerData.opacity; Accessible.name: "Pop-out opacity"; onMoved: backend.workTimer.setting("opacity",value) }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 350; spacing: 8
            Text { text: "Client & work"; font.bold: true; font.pixelSize: 15; color: Theme.ink }
            Caption { text: "Business" }
            Select { Layout.fillWidth: true; model: backend.state.businesses; currentIndex: backend.state.businessIndex; enabled: !backend.state.busy && panel.timerData.status==="idle"; onActivated: backend.selectBusiness(currentIndex) }
            Caption { text: "Client" }
            Select { Layout.fillWidth: true; model: backend.state.clients; textRole: "name"; currentIndex: panel.indexFor(model,panel.form.client); enabled: backend.state.catalogReady && !panel.timerData.saving; onActivated: backend.setField("timer","client",model[currentIndex].value) }
            GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 10; rowSpacing: 5
                Caption { text: "Project · optional" } Caption { text: "Service · optional" }
                Select { Layout.fillWidth: true; Layout.preferredWidth: 1; model: panel.form.projects; textRole: "name"; currentIndex: panel.indexFor(model,panel.form.project); enabled: !panel.timerData.saving; onActivated: backend.setField("timer","project",model[currentIndex].value) }
                Select { Layout.fillWidth: true; Layout.preferredWidth: 1; model: panel.form.services; textRole: "name"; currentIndex: panel.indexFor(model,panel.form.service); enabled: !panel.timerData.saving; onActivated: backend.setField("timer","service",model[currentIndex].value) }
            }
            Caption { text: "What are you working on?" }
            TextArea { Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 65; text: panel.form.note; color: Theme.ink; padding: 9; wrapMode: TextEdit.Wrap; selectByMouse: true; enabled: !panel.timerData.saving; Accessible.name: "Timer note"; background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 5 } onTextChanged: if(activeFocus)backend.setField("timer","note",text) }
            Check { text: "Billable"; checked: panel.form.billable; enabled: !panel.timerData.saving; onToggled: backend.setField("timer","billable",checked) }
            Item { Layout.fillHeight: true; Layout.maximumHeight: 8 }
        }
    }
    Popup {
        id: faceTray; objectName: "timerFaceTray"
        property var kinds: ["digital","flip","analog","station"]
        property var names: ["Digital stopwatch","Station flip","Classic stopwatch","Station stopwatch"]
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(460,parent.width-24); padding: 16; modal: true; focus: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: Theme.surface; border.color: Theme.line; radius: 10 }
        contentItem: ColumnLayout { spacing: 12
            RowLayout { Layout.fillWidth: true; Text { text: "Choose a timer face"; color: Theme.ink; font.bold: true; font.pixelSize: 17 } Item { Layout.fillWidth: true } AppButton { glyph: "close"; quiet: true; Accessible.name: "Close face chooser"; onClicked: faceTray.close() } }
            GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 10; rowSpacing: 10
                Repeater { model: 4
                    Button { id: choice; required property int index; objectName: "faceChoice"+index; Layout.fillWidth: true; implicitHeight: 165; padding: 8; Accessible.name: faceTray.names[index]
                        background: Rectangle { color: panel.timerData.face===faceTray.kinds[choice.index] ? Theme.selected : Theme.page; border.color: Theme.line; radius: 7 }
                        contentItem: ColumnLayout { ClockFace { Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 112; Layout.preferredHeight: analog ? 112 : 65; kind: faceTray.kinds[choice.index]; active: faceTray.opened } Text { Layout.alignment: Qt.AlignHCenter; text: faceTray.names[choice.index]; color: Theme.ink; font.pixelSize: 13 } }
                        onClicked: { backend.workTimer.setting("face",faceTray.kinds[index]); faceTray.close() }
                    }
                }
            }
        }
    }
}
