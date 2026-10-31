import QtQuick

import QtQuick.Controls

import QtQuick.Layouts

import QtQuick.Window

ApplicationWindow {

    id: window

    objectName: "mainWindow"

    title: backend.state.demo ? "FreshTray — Offline preview" : "FreshTray"

    visible: false

    flags: Qt.Window | Qt.FramelessWindowHint

    color: "transparent"

    font.family: "IBM Plex Sans"

    font.pixelSize: 13

    property string page: backend.state.panel

    property bool started: false

    property bool animateResize: false

    property bool animating: resizeWidth.running || resizeHeight.running

    property bool reducedMotion: backend.reducedMotion

    property var bounds: ({x:0,y:0,width:1200,height:800})

    minimumWidth: Math.min(page==="month" ? 778 : 540,bounds.width)

    minimumHeight: Math.min(page==="month" ? (width<778 ? 780 : 490) : 490,bounds.height)

    width: 620; height: 620

    Behavior on width { enabled: window.animateResize; NumberAnimation { id: resizeWidth; duration: window.started && !window.reducedMotion ? 180 : 0; easing.type: Easing.InOutCubic } }

    Behavior on height { enabled: window.animateResize; NumberAnimation { id: resizeHeight; duration: window.started && !window.reducedMotion ? 180 : 0; easing.type: Easing.InOutCubic } }

    function fitPanel(keepWidth) {

        bounds=backend.windowBounds()

        if(visibility===Window.Maximized || visibility===Window.FullScreen) return

        animateResize=started && !reducedMotion

        resizeGuard.restart()

        let w=keepWidth ? width : page==="month" ? 1040 : page==="settings" ? 720 : 620

        let h=page==="month" ? 710 : page==="settings" ? 660 : 650
        if(page==="settings" && backend.state.connectionSection) {
            const chrome=43+1+46
                         +(Theme.compact ? 8 : 12)+(Theme.compact ? 6 : 21)+settingsHeading.implicitHeight+(Theme.compact ? 6 : 8)+2
            h=Math.max(490,Math.ceil(chrome+settingsView.naturalHeight+8))
        }


        w=Math.min(w,bounds.width-16)

        if(page==="month" && w<778) h=850

        height=Math.min(h,bounds.height-16)

        if(!keepWidth) width=w

        if(backend.state.settings.docked_mode) {

            x=bounds.x+bounds.width-w-8; y=bounds.y+bounds.height-height-8

        } else {

            x=Math.max(bounds.x,Math.min(x,bounds.x+bounds.width-w))

            y=Math.max(bounds.y,Math.min(y,bounds.y+bounds.height-height))

        }

    }

    Timer {
        id: settingsRefit
        objectName: "settingsRefitTimer"
        interval: 20
        onTriggered: {
            if(window.page!=="settings") return
            if(resizeWidth.running) restart()
            else window.fitPanel(true)
        }
    }

    Timer { id: resizeGuard; interval: 220; onTriggered: window.animateResize=false }

    onScreenChanged: if(started) fitPanel()

    onWidthChanged: if(started && backend.state.settings.docked_mode) x=bounds.x+bounds.width-width-8

    onHeightChanged: if(started && backend.state.settings.docked_mode) y=bounds.y+bounds.height-height-8

    onClosing: function(event) { event.accepted=false; backend.closeRequested() }

    Binding { target: Theme; property: "dark"; value: backend.state.settings.theme==="dark" || (backend.state.settings.theme==="system" && Application.styleHints.colorScheme===Qt.Dark) }

    Binding { target: Theme; property: "compact"; value: window.height<600 }

    Connections {

        target: backend

        function onFitRequested() { window.fitPanel(); if(window.page==="settings") settingsRefit.restart() }

        function onToast(message) { toastText.text=message; toast.visible=true; toastTimer.restart() }

        function onError(message) { if(!window.visible) { window.show(); window.requestActivate() } errorText.text=message; errorDialog.open() }

        function onConfirmation(title,message) { confirmDialog.title=title; confirmText.text=message; confirmDialog.open() }

        function onReminder() { reminderWindow.present() }

    }

    Rectangle {

        anchors.fill: parent; radius: window.visibility===Window.Maximized ? 0 : 10

        color: Theme.page; border.color: Theme.line

        ColumnLayout {

            anchors.fill: parent; anchors.margins: 1; spacing: 0

            Rectangle {

                objectName: "appTitleBar"
                Layout.fillWidth: true; Layout.minimumHeight: 43; Layout.preferredHeight: 43; Layout.maximumHeight: 43

                color: Theme.surface; radius: 9

                RowLayout {

                    anchors.fill: parent; anchors.leftMargin: 17; anchors.rightMargin: 7; spacing: 3

                    Wordmark { objectName: "mainWordmark" }

                    Item {

                        Layout.fillWidth: true; Layout.fillHeight: true

                        DragHandler { target: null; onActiveChanged: if(active) { window.animateResize=false; resizeWidth.stop(); resizeHeight.stop(); window.startSystemMove() } }

                        TapHandler { onDoubleTapped: window.visibility===Window.Maximized ? window.showNormal() : window.showMaximized() }

                    }

                    AppButton { glyph: "minimize"; Accessible.name: "Minimize"; quiet: true; implicitHeight: 28; onClicked: window.showMinimized() }

                    AppButton { glyph: "maximize"; Accessible.name: "Maximize or restore"; quiet: true; implicitHeight: 28; onClicked: window.visibility===Window.Maximized ? window.showNormal() : window.showMaximized() }

                    AppButton { glyph: "close"; Accessible.name: backend.state.settings.close_to_tray ? "Hide to tray" : "Quit FreshTray"; quiet: true; implicitHeight: 28; onClicked: backend.closeRequested() }

                }

            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }

            RowLayout {
                objectName: "mainTabStrip"
                Layout.fillWidth: true; Layout.minimumHeight: 46; Layout.preferredHeight: 46; Layout.maximumHeight: 46
                Layout.leftMargin: 14; Layout.rightMargin: 14; spacing: 4
                z: 2
                Repeater {
                    model: [{key:"log",label:"Log time"},{key:"month",label:"Monthly hours"},{key:"settings",label:"Settings"}]
                    Button {
                        id: folderTab
                        required property var modelData
                        property bool selected: window.page===modelData.key
                        objectName: modelData.key+"Tab"
                        Layout.alignment: Qt.AlignBottom
                        Layout.preferredHeight: selected ? 35 : 31
                        Layout.preferredWidth: 122
                        text: modelData.label
                        Accessible.role: Accessible.PageTab
                        Accessible.name: text
                        contentItem: Text { text: folderTab.text; color: folderTab.selected ? Theme.blue : Theme.muted; font.pixelSize: 13; font.bold: folderTab.selected; font.underline: false; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        background: Canvas {
                            id: folderShape
                            property color fillColor: folderTab.selected ? Theme.surface : folderTab.hovered ? Theme.hover : Theme.page
                            property color edgeColor: Theme.line
                            onFillColorChanged: requestPaint()
                            onEdgeColorChanged: requestPaint()
                            onWidthChanged: requestPaint()
                            onHeightChanged: requestPaint()
                            Connections { target: folderTab; function onSelectedChanged() { folderShape.requestPaint() } }
                            onPaint: {
                                const c=getContext("2d"); c.reset()
                                c.beginPath(); c.moveTo(.5,height); c.lineTo(.5,8)
                                c.quadraticCurveTo(.5,.5,8,.5); c.lineTo(width-14,.5)
                                c.quadraticCurveTo(width-12,.5,width-10.5,2)
                                c.lineTo(width-2,10.5)
                                c.quadraticCurveTo(width-.5,12,width-.5,14); c.lineTo(width-.5,height)
                                c.fillStyle=fillColor; c.fill()
                                if(!folderTab.selected) { c.lineTo(.5,height-.5) }
                                c.strokeStyle=edgeColor; c.lineWidth=1; c.stroke()
                            }
                        }
                        Rectangle { visible: folderTab.selected; x: 1; y: parent.height-1; width: parent.width-2; height: 3; color: Theme.surface }
                        onClicked: backend.selectPanel(modelData.key)
                    }
                }
                Item { Layout.fillWidth: true }
                AppButton {
                    objectName: "syncStatus"
                    visible: !backend.state.demo && backend.state.connected && (backend.state.sync.count>0 || backend.state.sync.online===false || backend.state.sync.message.length>0)
                    quiet: true; implicitHeight: 28; Layout.maximumWidth: 190
                    text: backend.state.sync.problems.length>0 ? (window.width<650 ? "Review sync" : "Sync needs review") : backend.state.sync.online===false ? (window.width<650 ? "Offline" : "Offline · "+backend.state.sync.count+" waiting") : (backend.state.sync.count>0 ? backend.state.sync.count+(window.width<650 ? " waiting" : " waiting to sync") : "Cached data")
                    tip: backend.state.sync.message || "Changes are saved on this PC. Open connection settings to review sync."
                    onClicked: backend.showSync()
                }
                BusyIndicator { running: backend.state.busy; visible: running; Layout.alignment: Qt.AlignVCenter; Layout.preferredWidth: 23; Layout.preferredHeight: 23 }
            }

            Item {

                id: panelHost

                objectName: "panelHost"

                Layout.fillWidth: true; Layout.fillHeight: true

                Layout.leftMargin: 26; Layout.rightMargin: 26; Layout.topMargin: Theme.compact ? 8 : 12; Layout.bottomMargin: Theme.compact ? 6 : 21

                clip: false
                Rectangle {
                    objectName: "folderPanel"
                    anchors.fill: parent; anchors.leftMargin: -12; anchors.rightMargin: -12
                    anchors.topMargin: -panelHost.Layout.topMargin
                    anchors.bottomMargin: -Math.min(12, Math.max(0, panelHost.Layout.bottomMargin-2))
                    radius: 0; color: Theme.surface
                    PanelOutline { objectName: "folderOutline"; anchors.fill: parent; radius: 0 }
                    z: -1
                }

                // All three panels stay alive; switching never rebuilds the form.

                ColumnLayout {

                    id: logPanel; objectName: "logPanel"; clip: true

                    anchors.fill: parent; spacing: Theme.compact ? 3 : 9; visible: window.page==="log"

                    Text { text: "Log your day"; font.pixelSize: Theme.compact ? 22 : 26; font.bold: true; color: Theme.ink }


                    Card {
                        objectName: "businessCard"
                        Layout.fillWidth: true
                        GridLayout {
                            anchors.fill: parent; columns: Theme.compact ? 2 : 1
                            rowSpacing: 5; columnSpacing: 12
                            Text { text: "Business"; color: Theme.ink; font.pixelSize: 15; font.bold: true }
                            Select { objectName: "businessChoice"; Layout.fillWidth: true; model: backend.state.businesses; currentIndex: backend.state.businessIndex; enabled: !backend.state.busy; onActivated: backend.selectBusiness(currentIndex) }
                        }
                    }

                    Card {
                        objectName: "logEditorCard"
                        Layout.fillWidth: true; Layout.fillHeight: true

                        EntryForm { objectName: "logForm"; anchors.fill: parent; scope: "log" }

                        Skeleton { anchors.fill: parent; active: backend.state.loading==="catalog" }

                    }

                    Text { Layout.fillWidth: true; visible: !!backend.state.warning; text: backend.state.warning; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11 }

                    AppButton { visible: !backend.state.connected; text: "Connect FreshBooks"; onClicked: backend.selectPanel("settings") }

                }

                MonthPanel { objectName: "monthPanel"; clip: true; anchors.fill: parent; visible: window.page==="month" }

                ColumnLayout {

                    anchors.fill: parent; clip: true; visible: window.page==="settings"; spacing: Theme.compact ? 6 : 8

                    Text { id: settingsHeading; text: "Settings"; font.pixelSize: Theme.compact ? 22 : 26; font.bold: true; color: Theme.ink }

                    SettingsPanel {
                        id: settingsView; objectName: "settingsPanel"
                        Layout.fillWidth: true; Layout.fillHeight: true
                        onNaturalHeightChanged: if(window.started && window.page==="settings" && backend.state.connectionSection) settingsRefit.restart()
                    }

                }

                Rectangle {

                    id: transitionVeil

                    anchors.fill: parent; color: Theme.surface

                    visible: window.animating || settingsRefit.running

                    Text { anchors.centerIn: parent; text: window.page==="log" ? "Log your day" : window.page==="month" ? "Monthly hours" : "Settings"; color: Theme.muted; font.pixelSize: 16 }

                }

            }

        }

    }

    // Native window-manager resizing; no manual drawing or scaling on drag.

    Repeater {

        model: [Qt.TopEdge,Qt.BottomEdge,Qt.LeftEdge,Qt.RightEdge,Qt.TopEdge|Qt.LeftEdge,Qt.TopEdge|Qt.RightEdge,Qt.BottomEdge|Qt.LeftEdge,Qt.BottomEdge|Qt.RightEdge]

        MouseArea {

            required property int modelData

            z: 50

            width: (modelData&Qt.LeftEdge || modelData&Qt.RightEdge) ? 5 : window.width-10

            height: (modelData&Qt.TopEdge || modelData&Qt.BottomEdge) ? 5 : window.height-10

            x: modelData&Qt.RightEdge ? window.width-width : modelData&Qt.LeftEdge ? 0 : 5

            y: modelData&Qt.BottomEdge ? window.height-height : modelData&Qt.TopEdge ? 0 : 5

            enabled: window.visibility!==Window.Maximized && !backend.state.settings.docked_mode

            cursorShape: (modelData===(Qt.TopEdge|Qt.LeftEdge) || modelData===(Qt.BottomEdge|Qt.RightEdge)) ? Qt.SizeFDiagCursor : (modelData===(Qt.TopEdge|Qt.RightEdge) || modelData===(Qt.BottomEdge|Qt.LeftEdge)) ? Qt.SizeBDiagCursor : (modelData&Qt.LeftEdge || modelData&Qt.RightEdge) ? Qt.SizeHorCursor : Qt.SizeVerCursor

            onPressed: { window.animateResize=false; resizeWidth.stop(); resizeHeight.stop(); window.startSystemResize(modelData) }

        }

    }

    Rectangle {

        id: toast; visible: false; z: 100

        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 17; anchors.topMargin: 96

        width: Math.min(window.width-34,toastText.implicitWidth+32); height: 43; radius: 8

        color: Theme.dark ? "#194b35" : "#edfaef"; border.color: Theme.dark ? "#3e7953" : "#a6d7b0"

        Text { id: toastText; anchors.centerIn: parent; width: parent.width-25; elide: Text.ElideRight; color: Theme.ink; font.pixelSize: 13 }

        Timer { id: toastTimer; interval: 3500; onTriggered: toast.visible=false }

    }

    Dialog {

        id: errorDialog; objectName: "errorDialog"; parent: Overlay.overlay; modal: true

        x: (window.width-width)/2; y: (window.height-height)/2; width: Math.min(440,window.width-40)

        title: "FreshTray"

        header: Text { text: "FreshTray"; color: Theme.ink; font.bold: true; font.pixelSize: 15; padding: 16 }

        footer: Item { implicitHeight: 52; RowLayout { anchors.fill: parent; anchors.margins: 10; Item { Layout.fillWidth: true } AppButton { text: "OK"; primary: true; onClicked: errorDialog.accept() } } }

        background: Rectangle { radius: 9; color: Theme.surface; border.color: Theme.line }

        contentItem: Text { id: errorText; color: Theme.ink; wrapMode: Text.WordWrap; font.pixelSize: 14 }

    }

    Dialog {

        id: confirmDialog; objectName: "confirmDialog"; parent: Overlay.overlay; modal: true

        x: (window.width-width)/2; y: (window.height-height)/2; width: Math.min(440,window.width-40)

        header: Text { text: confirmDialog.title; color: Theme.ink; font.bold: true; font.pixelSize: 15; padding: 16 }

        footer: Item { implicitHeight: 52; RowLayout { anchors.fill: parent; anchors.margins: 10; Item { Layout.fillWidth: true } AppButton { text: "Cancel"; onClicked: confirmDialog.reject() } AppButton { text: confirmDialog.title==="Delete time entry" ? "Delete entry" : "Continue"; primary: confirmDialog.title!=="Delete time entry"; onClicked: confirmDialog.accept() } } }

        background: Rectangle { radius: 9; color: Theme.surface; border.color: Theme.line }

        contentItem: Text { id: confirmText; color: Theme.ink; wrapMode: Text.WordWrap; font.pixelSize: 14 }

        onAccepted: backend.answer(true)

        onRejected: backend.answer(false)

    }

    Window {
        id: reminderWindow; objectName: "reminderWindow"
        width: 400; height: 390; visible: false
        title: "FreshTray reminder"
        flags: Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        color: "transparent"
        property bool presenting: false
        property bool presented: false
        property bool entering: reminderEntrance.running
        property real destinationY: 0
        property real entranceY: 0
        function savePosition() { backend.rememberReminderPosition(Math.round(x),Math.round(y)) }
        function present() {
            if(!visible) {
                presenting=true
                rememberPosition.stop()
                reminderDial.captureTime()
                const placement=backend.reminderPlacement(400,390)
                width=placement.width; height=placement.height
                x=placement.x; y=placement.y
                destinationY=placement.y
                entranceY=Math.min(destinationY+12,placement.bottom)
                opacity=window.reducedMotion ? 1 : 0
                presented=true
                show()
                backend.reminderOpened()
                if(!window.reducedMotion) reminderEntrance.start()
                presenting=false
            }
            raise(); requestActivate()
        }
        function beginDrag() {
            reminderEntrance.stop(); opacity=1
            rememberPosition.stop()
            startSystemMove()
        }
        onXChanged: if(presented && visible && !presenting && !entering) rememberPosition.restart()
        onYChanged: if(presented && visible && !presenting && !entering) rememberPosition.restart()
        onVisibleChanged: if(!visible && presented) {
            rememberPosition.stop()
            if(entering) { reminderEntrance.stop(); y=destinationY }
            savePosition()
            opacity=1
        }
        Timer { id: rememberPosition; interval: 300; onTriggered: if(reminderWindow.visible && !reminderWindow.entering) reminderWindow.savePosition() }
        ParallelAnimation {
            id: reminderEntrance
            NumberAnimation { target: reminderWindow; property: "opacity"; from: 0; to: 1; duration: 240; easing.type: Easing.OutCubic }
            NumberAnimation { target: reminderWindow; property: "y"; from: reminderWindow.entranceY; to: reminderWindow.destinationY; duration: 280; easing.type: Easing.OutCubic }
        }
        Rectangle {
            anchors.fill: parent; radius: 14; color: Theme.surface; border.color: Theme.line
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 20; spacing: 8
                RowLayout {
                    Layout.fillWidth: true; spacing: 6
                    Wordmark { objectName: "reminderWordmark" }
                    Item { Layout.fillWidth: true }
                    Item { Layout.preferredWidth: 110; Layout.preferredHeight: 34
                        Row {
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            Grid { anchors.verticalCenter: parent.verticalCenter; columns: 3; spacing: 3
                                Repeater { model: 6; Rectangle { width: 3; height: 3; radius: 1.5; color: Theme.muted } }
                            }
                            Caption { text: "Drag to move"; font.pixelSize: 11 }
                        }
                        MouseArea { objectName: "reminderDragHandle"; anchors.fill: parent; hoverEnabled: true; cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor; onPressed: reminderWindow.beginDrag() }
                    }
                }
                PunchClock { id: reminderDial; objectName: "reminderPunchClock"; Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 140; animate: reminderWindow.visible && !window.reducedMotion }
                Text { Layout.fillWidth: true; text: "Time to log your hours"; horizontalAlignment: Text.AlignHCenter; color: Theme.ink; font.family: "IBM Plex Sans"; font.pixelSize: 20; font.bold: true }
                Caption { Layout.fillWidth: true; text: "Add today's work to FreshBooks."; horizontalAlignment: Text.AlignHCenter }
                RowLayout {
                    Layout.fillWidth: true; Layout.topMargin: 10; spacing: 10
                    AppButton { objectName: "reminderLater"; text: "Later"; Layout.fillWidth: true; Layout.preferredWidth: 1; onClicked: reminderWindow.hide() }
                    AppButton { objectName: "reminderAgain"; text: "Remind me"; Layout.fillWidth: true; Layout.preferredWidth: 1; tip: "Show again in " + backend.state.settings.remind_me_minutes + " minutes"; onClicked: if(backend.remindMe()) reminderWindow.hide() }
                    AppButton { objectName: "reminderLog"; text: "Log hours"; primary: true; glyph: "check"; Layout.fillWidth: true; Layout.preferredWidth: 1; onClicked: { reminderWindow.hide(); backend.logFromReminder() } }
                }
            }
        }
    }

    Shortcut { sequence: "Ctrl+1"; onActivated: backend.selectPanel("log") }

    Shortcut { sequence: "Ctrl+2"; onActivated: backend.selectPanel("month") }

    Shortcut { sequence: "Ctrl+3"; onActivated: backend.selectPanel("settings") }

    Component.onCompleted: {

        fitPanel()

        if(!backend.state.settings.docked_mode) { x=bounds.x+(bounds.width-width)/2; y=bounds.y+(bounds.height-height)/2 }

        started=true

    }

}
