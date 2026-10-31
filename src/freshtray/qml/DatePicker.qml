import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Popup {
    id: picker
    property string selected: ""
    property date cursor: new Date()
    signal picked(string day)
    width: 294; height: 294
    padding: 14
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: { const parts=selected.split("-"); cursor=parts.length===3 ? new Date(+parts[0],+parts[1]-1,+parts[2],12) : new Date() }
    background: Rectangle { color: Theme.surface; radius: 9; border.color: Theme.line }
    ColumnLayout {
        anchors.fill: parent; spacing: 5
        RowLayout {
            AppButton { glyph: "left"; tip: "Previous month"; onClicked: picker.cursor=new Date(picker.cursor.getFullYear(),picker.cursor.getMonth()-1,1,12) }
            Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: Qt.formatDate(picker.cursor,"MMMM yyyy"); color: Theme.ink; font.pixelSize: 14; font.bold: true }
            AppButton { glyph: "right"; tip: "Next month"; onClicked: picker.cursor=new Date(picker.cursor.getFullYear(),picker.cursor.getMonth()+1,1,12) }
        }
        DayOfWeekRow { Layout.fillWidth: true; locale: Qt.locale("en_US"); delegate: Text { required property string shortName; text: shortName; color: Theme.muted; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12 } }
        MonthGrid {
            Layout.fillWidth: true; Layout.fillHeight: true
            month: picker.cursor.getMonth(); year: picker.cursor.getFullYear(); locale: Qt.locale("en_US")
            delegate: Rectangle {
                required property var model
                color: Qt.formatDate(model.date,"yyyy-MM-dd")===picker.selected ? Theme.selected : "transparent"
                radius: 5
                Text { anchors.centerIn: parent; text: parent.model.day; color: parent.model.month===picker.cursor.getMonth() ? Theme.ink : Theme.muted; font.pixelSize: 13; opacity: parent.model.date>new Date() ? .3 : 1 }
            }
            onClicked: function(day) { if(day<=new Date()) { picker.picked(Qt.formatDate(day,"yyyy-MM-dd")); picker.close() } }
        }
    }
}
