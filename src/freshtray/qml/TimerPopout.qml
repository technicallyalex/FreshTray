import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Window {
    id: pop
    objectName: "timerPopout"
    property var timerData: backend.workTimer.state
    property bool ready: false
    property bool adjusting: false
    property bool dragging: false
    property bool moved: false
    property point pressPoint
    property point pressPosition
    property bool showHint: ready && visible && timerData.condensed && clockMouse.containsMouse && !dragging && hintHasSpace
    property bool hintHasSpace: true
    transientParent: null
    title: "FreshTray timer"
    visible: timerData.popout
    flags: Qt.Tool | Qt.FramelessWindowHint | (timerData.pinned ? Qt.WindowStaysOnTopHint : 0)
    color: "transparent"
    opacity: hover.hovered || dragging ? 1 : timerData.opacity
    width: timerData.condensed ? (clock.analog ? 170 : 224) : 260
    height: timerData.condensed ? (clock.analog ? 170 : 108) : Math.ceil(body.implicitHeight+20)
    function constrain() {
        if(!ready || adjusting)return
        adjusting=true
        const p=backend.workTimer.constrainPosition(x,y,width,height)
        x=p.x;y=p.y;adjusting=false
        positionHint()
    }
    function positionHint() {
        const p=backend.workTimer.constrainPosition(x,y,width,height)
        const above=y-hint.height-9>=p.top
        hintHasSpace=above || y+height+hint.height+9<=p.bottom
        const h=backend.workTimer.constrainPosition(Math.round(x+(width-hint.width)/2),above ? y-hint.height-9 : y+height+9,hint.width,hint.height)
        hint.x=h.x;hint.y=h.y
    }
    function begin(mouse,area) {
        dragging=true;moved=false;pressPoint=area.mapToGlobal(mouse.x,mouse.y);pressPosition=Qt.point(x,y)
    }
    function move(mouse,area) {
        if(!dragging)return
        const point=area.mapToGlobal(mouse.x,mouse.y),dx=point.x-pressPoint.x,dy=point.y-pressPoint.y
        if(Math.abs(dx)+Math.abs(dy)>4)moved=true
        const p=backend.workTimer.constrainPosition(Math.round(pressPosition.x+dx),Math.round(pressPosition.y+dy),width,height)
        x=p.x;y=p.y
    }
    onClosing: function(event) { event.accepted=false;backend.workTimer.setting("popout",false) }
    onXChanged: if(ready) { constrain();savePosition.restart() }
    onYChanged: if(ready) { constrain();savePosition.restart() }
    onWidthChanged: if(ready)Qt.callLater(constrain)
    onHeightChanged: if(ready)Qt.callLater(constrain)
    onScreenChanged: if(ready)Qt.callLater(constrain)
    onShowHintChanged: if(showHint)positionHint()
    Timer { id: savePosition; interval: 400; onTriggered: backend.workTimer.position(pop.x,pop.y) }
    Component.onCompleted: {
        const saved=backend.workTimer.savedPosition,area=backend.windowBounds()
        x=saved.x===undefined ? area.x+area.width-width-24 : saved.x
        y=saved.y===undefined ? area.y+80 : saved.y
        ready=true;constrain()
    }
    Rectangle {
        anchors.fill: parent; radius: 10; color: pop.timerData.condensed && clock.analog ? "transparent" : Theme.surface; border.color: pop.timerData.condensed && clock.analog ? "transparent" : Theme.line
        HoverHandler { id: hover }
        ColumnLayout {
            id: body; anchors.fill: parent; anchors.margins: pop.timerData.condensed ? 3 : 10; spacing: 8
            RowLayout {
                objectName: "timerPopoutTitlebar"
                Layout.fillWidth: true; Layout.preferredHeight: 28; visible: !pop.timerData.condensed; spacing: 3
                Item { Layout.fillWidth: true }
                AppButton { objectName: "timerCondense"; glyph: "condense"; implicitWidth: 28; implicitHeight: 28; quiet: true; Accessible.name: "Timer only"; onClicked: backend.workTimer.setting("condensed",true) }
                AppButton { objectName: "timerPin"; glyph: "pin"; implicitWidth: 28; implicitHeight: 28; quiet: true; selected: pop.timerData.pinned; Accessible.name: "Keep timer on top"; onClicked: backend.workTimer.setting("pinned",!pop.timerData.pinned) }
                AppButton { objectName: "timerPopoutClose"; glyph: "close"; implicitWidth: 28; implicitHeight: 28; quiet: true; Accessible.name: "Close timer pop-out"; onClicked: backend.workTimer.setting("popout",false) }
                Item {
                    Layout.preferredWidth: 28; Layout.preferredHeight: 28
                    Icon { anchors.centerIn: parent; name: "grip"; ink: Theme.muted }
                    MouseArea { id: grip; objectName: "timerPopoutGrip"; anchors.fill: parent; hoverEnabled: true; cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        onPressed: function(mouse){pop.begin(mouse,grip)}
                        onPositionChanged: function(mouse){if(pressed)pop.move(mouse,grip)}
                        onReleased: pop.dragging=false
                        onCanceled: pop.dragging=false
                    }
                }
            }
            Text { visible: !pop.timerData.condensed; Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: pop.width-24; elide: Text.ElideRight; text: { const c=backend.state.clients.find(c=>c.value===backend.state.timerForm.client);return c ? c.name : "" } color: Theme.ink; font.pixelSize: 13; font.bold: true }
            ClockFace {
                id: clock; objectName: "timerPopoutClock"; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: pop.timerData.condensed ? (analog?164:216) : 200; Layout.preferredHeight: analog ? width : 94; kind: pop.timerData.face; active: pop.visible
                MouseArea { id: clockMouse; objectName: "timerCondensedMouse"; anchors.fill: parent; enabled: pop.timerData.condensed; hoverEnabled: true; cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    onPressed: function(mouse){pop.begin(mouse,clockMouse)}
                    onPositionChanged: function(mouse){if(pressed)pop.move(mouse,clockMouse)}
                    onReleased: { const clicked=!pop.moved;pop.dragging=false;if(clicked)backend.workTimer.setting("condensed",false) }
                    onCanceled: pop.dragging=false
                }
            }
            TimerControls { visible: !pop.timerData.condensed; Layout.fillWidth: true; compact: true }
        }
    }
    Window {
        id: hint; objectName: "timerMoveHint"; transientParent: pop
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint
        color: "transparent"; width: hintText.implicitWidth+24; height: hintText.implicitHeight+18
        opacity: pop.showHint ? 1 : 0
        visible: pop.showHint || hintFade.running
        Behavior on opacity { NumberAnimation { id: hintFade; duration: backend.reducedMotion ? 0 : 150 } }
        Rectangle { anchors.fill: parent; radius: 7; color: Theme.surface; border.color: Theme.line
            Text { id: hintText; anchors.centerIn: parent; text: "Click for controls · drag to move"; color: Theme.ink; font.family: "IBM Plex Sans"; font.pixelSize: 12 }
        }
    }
}
