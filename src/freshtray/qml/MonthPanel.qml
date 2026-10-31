import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: panel
    spacing: Theme.compact ? 6 : 10
    property var s: backend.state
    FontMetrics { id: entryMetrics; font.family: "IBM Plex Sans"; font.pixelSize: 12 }
    readonly property int entryRowHeight: Math.max(52, Math.ceil(entryMetrics.height)*2+18)
    // Reserve against the loaded month, never the currently selected day.
    readonly property int pageSize: Theme.compact ? 1 : 2
    onPageSizeChanged: backend.setEntryPageSize(pageSize)
    Component.onCompleted: backend.setEntryPageSize(pageSize)
    readonly property int reservedRows: Math.min(pageSize,Math.max(1,backend.calendar.reduce(function(n,day) { return Math.max(n,day.entryCount || 0) },0)))
    readonly property bool reservePager: backend.calendar.some(function(day) { return day.entryCount>panel.pageSize })
    readonly property int entryAreaHeight: reservedRows*entryRowHeight+(reservedRows-1)*4+(reservePager ? 30 : 0)

    property var months: ["January","February","March","April","May","June","July","August","September","October","November","December"]
    RowLayout {
        Layout.fillWidth: true; spacing: 6
        AppButton { glyph: "left"; tip: "Previous month"; enabled: !panel.s.busy; onClicked: backend.shiftMonth(-1) }
        AppButton { glyph: "right"; tip: "Next month"; enabled: !panel.s.busy; onClicked: backend.shiftMonth(1) }
        Select { objectName: "monthChoice"; Layout.preferredWidth: 134; model: panel.months; currentIndex: panel.s.month-1; enabled: !panel.s.busy; onActivated: backend.chooseMonth(panel.s.year,currentIndex+1) }
        Select { objectName: "yearChoice"; Layout.preferredWidth: 84; model: panel.s.years; currentIndex: model.indexOf(String(panel.s.year)); enabled: !panel.s.busy; onActivated: backend.chooseMonth(Number(currentText),panel.s.month) }
        AppButton { text: "Today"; enabled: !panel.s.busy; onClicked: backend.today() }
        Item { Layout.fillWidth: true }
    }
    GridLayout {
        id: body
        Layout.fillWidth: true; Layout.fillHeight: true
        columns: panel.width>=720 ? 2 : 1
        columnSpacing: 16; rowSpacing: 10
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.preferredWidth: 580
            spacing: 8
            Rectangle {
                id: calendarBox
                objectName: "monthlyCalendar"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.minimumHeight: body.columns===2 ? 200 : 180
                Layout.preferredHeight: 340
                color: Theme.surface; radius: 8; border.color: Theme.line
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    RowLayout {
                        Layout.fillWidth: true; spacing: 0
                        Repeater { model: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat","Total"]
                            Text { required property string modelData; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 29; text: modelData; color: Theme.muted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredHeight: 300; spacing: 0
                        GridLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 7
                            columns: 7; columnSpacing: 0; rowSpacing: 0
                            Repeater {
                                model: backend.calendar
                                Rectangle {
                                    required property var modelData
                                    objectName: "calendarDay"
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    Layout.preferredWidth: 1; Layout.preferredHeight: 1
                                    color: modelData.selected ? Theme.selected : modelData.current ? Theme.surface : Theme.page
                                    border.color: modelData.selected ? Theme.blue : Theme.line
                                    border.width: modelData.selected ? 2 : .5
                                    Text { x: 7; y: Theme.compact ? 2 : 5; text: parent.modelData.day; color: parent.modelData.today ? Theme.blue : Theme.muted; font.pixelSize: Theme.compact ? 10 : 11; font.bold: parent.modelData.today; opacity: parent.modelData.current ? 1 : .3 }
                                    Text { anchors.centerIn: parent; anchors.verticalCenterOffset: Theme.compact ? 6 : 4; text: parent.modelData.hours; color: Theme.ink; font.pixelSize: Theme.compact || calendarBox.width<440 ? 12 : 14; font.bold: true }
                                    Row { anchors.right: parent.right; anchors.rightMargin: 5; y: 8; spacing: 2
                                        Repeater { model: Math.min(3,modelData.entryCount)
                                            Rectangle { width: 4; height: 4; radius: 2; color: Theme.blue }
                                        }
                                    }
                                    MouseArea { id: dayHit; anchors.fill: parent; hoverEnabled: true; enabled: parent.modelData.current && !panel.s.busy; cursorShape: Qt.PointingHandCursor; onClicked: backend.selectDay(parent.modelData.iso) }
                                    ToolTip.visible: dayHit.containsMouse && modelData.entryCount>0
                                    ToolTip.text: modelData.entryCount + (modelData.entryCount===1 ? " time entry" : " time entries")
                                    Accessible.role: Accessible.Button
                                    Accessible.name: modelData.iso + (modelData.hasEntry ? ", " + modelData.hours + " hours logged in " + modelData.entryCount + " entries" : ", no entries")
                                    activeFocusOnTab: modelData.current
                                    Keys.onReturnPressed: backend.selectDay(modelData.iso)
                                    Keys.onSpacePressed: backend.selectDay(modelData.iso)
                                }
                            }
                        }
                        ColumnLayout {
                            Layout.fillHeight: true; Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 0
                            Repeater { model: panel.s.weeks
                                Rectangle { required property string modelData; Layout.fillHeight: true; Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.totalSurface; border.color: Theme.line; border.width: .5
                                    Text { anchors.centerIn: parent; text: parent.modelData; color: Theme.totalInk; font.pixelSize: 12; font.bold: true }
                                }
                            }
                        }
                    }
                    RowLayout {
                        objectName: "calendarTotalsFooter"
                        Layout.fillWidth: true; Layout.fillHeight: false; Layout.minimumHeight: 36; Layout.maximumHeight: 36; Layout.preferredHeight: 36; spacing: 0
                        Rectangle { Layout.fillWidth: true; Layout.preferredWidth: 7; Layout.fillHeight: true; color: Theme.page; border.color: Theme.line; border.width: .5
                            Caption { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "Monthly total" }
                        }
                        Rectangle { Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.fillHeight: true; color: Theme.totalSurface; border.color: Theme.line; border.width: .5
                            Text { objectName: "calendarMonthTotal"; anchors.centerIn: parent; text: panel.s.monthTotal; color: Theme.totalInk; font.pixelSize: 12; font.bold: true; Accessible.name: "Monthly total, " + text + " hours" }
                        }
                    }
                }
                PanelOutline { objectName: "calendarFrame"; anchors.fill: parent; radius: 8; fading: false; z: 2 }
                Skeleton { anchors.fill: parent; active: panel.s.loading==="month" }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: Qt.formatDate(new Date(panel.s.selected+"T12:00:00"),"ddd, MMM d"); color: Theme.ink; font.pixelSize: 13; font.bold: true }
                Item { Layout.fillWidth: true }
            }
            Item {
                objectName: "dayEntriesArea"
                Layout.fillWidth: true
                Layout.minimumHeight: panel.entryAreaHeight; Layout.preferredHeight: panel.entryAreaHeight; Layout.maximumHeight: panel.entryAreaHeight
                ColumnLayout {
                anchors.fill: parent; spacing: 0
                Repeater {
                    model: panel.s.entries.slice(panel.s.entryPage*panel.pageSize,panel.s.entryPage*panel.pageSize+panel.pageSize)
                    Card {
                        required property var modelData
                        required property int index
                        Layout.topMargin: index>0 ? 4 : 0
                        Layout.fillWidth: true; padding: 8
                        Layout.minimumHeight: panel.entryRowHeight; Layout.preferredHeight: panel.entryRowHeight; Layout.maximumHeight: panel.entryRowHeight
                        RowLayout {
                            anchors.fill: parent; spacing: 8
                            ColumnLayout { Layout.fillWidth: true; spacing: 2
                                Text { Layout.fillWidth: true; text: modelData.client; color: Theme.ink; font.pixelSize: 12; elide: Text.ElideRight }
                                Caption { Layout.fillWidth: true; text: modelData.note || "No note" }
                            }
                            Caption { text: modelData.hours+(modelData.sync ? (modelData.sync==="conflict" || modelData.sync==="review" ? " · Review" : " · Waiting") : modelData.billed ? " · Billed" : "") }
                            AppButton { text: "Edit"; implicitHeight: 29; enabled: !panel.s.busy && panel.s.monthReady && !modelData.restriction; onClicked: backend.editEntry(modelData.id) }
                            AppButton { text: "Delete"; tip: "Delete time entry"; implicitHeight: 29; quiet: true; enabled: !panel.s.busy && panel.s.monthReady && !modelData.restriction; onClicked: backend.deleteEntry(modelData.id)
                                contentItem: Text { text: "Delete"; color: Theme.dark ? "#ffb4b4" : "#b42332"; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            }
                        }
                    }
                }
                Caption { visible: panel.s.entries.length===0; text: panel.s.monthReady ? "No time logged for this day" : "Connect to load your hours"; Layout.preferredHeight: panel.entryRowHeight; Layout.maximumHeight: panel.entryRowHeight; verticalAlignment: Text.AlignVCenter }
                RowLayout { visible: panel.s.entries.length>panel.pageSize
                    Layout.topMargin: 4; Layout.minimumHeight: 26; Layout.maximumHeight: 26
                    AppButton { glyph: "left"; tip: "Previous entries"; implicitHeight: 26; enabled: panel.s.entryPage>0; onClicked: backend.entryPage(panel.s.entryPage-1) }
                    Caption { text: (panel.s.entryPage+1)+" / "+Math.ceil(panel.s.entries.length/panel.pageSize) }
                    AppButton { glyph: "right"; tip: "More entries"; implicitHeight: 26; enabled: (panel.s.entryPage+1)*panel.pageSize<panel.s.entries.length; onClicked: backend.entryPage(panel.s.entryPage+1) }
                }
                Item { Layout.fillHeight: true }
                }
            }
        }
        Card {
            objectName: "monthlyEditorCard"
            Layout.fillWidth: true; Layout.fillHeight: body.columns===2
            Layout.preferredWidth: 340
            Layout.minimumWidth: body.columns===2 ? 310 : 0
            EntryForm { id: monthlyForm; objectName: "monthlyEditor"; anchors.fill: parent; compact: true; scope: "month" }
            Skeleton { anchors.fill: parent; active: panel.s.loading==="catalog" || panel.s.loading==="entry" }
        }
    }
}
