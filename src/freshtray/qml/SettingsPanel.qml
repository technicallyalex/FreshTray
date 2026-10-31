import QtQuick

import QtQuick.Controls

import QtQuick.Layouts

Item {

    id: panel
    implicitHeight: settingsLayout.implicitHeight
    readonly property real naturalHeight: settingsLayout.implicitHeight

    property var draft: ({})

    property var s: backend.state
    property bool showConnectionSetup: false


    Component.onCompleted: draft=Object.assign({},backend.state.settings)

    Connections { target: backend; function onPreferencesChanged() { panel.draft=Object.assign({},backend.state.settings) } }

    function change(key,value) { backend.applySetting(key,value) }

    PanelOutline {
        objectName: "settingsSectionOutline"
        radius: 0
        anchors.left: parent.left; anchors.right: parent.right
        y: settingsTabs.y+settingsTabs.height
        height: Math.max(0,parent.height-y)
    }
    ColumnLayout {
        id: settingsLayout
        anchors.fill: parent; spacing: Theme.compact ? 4 : 12

    RowLayout {
        id: settingsTabs
        Layout.preferredHeight: Theme.compact ? 30 : 35
        z: 2
        Layout.fillWidth: true

        SectionTab { objectName: "preferencesSectionTab"; text: "Preferences"; Layout.alignment: Qt.AlignBottom; selected: !panel.s.connectionSection; onClicked: backend.connectionSection(false) }

        SectionTab { objectName: "connectionSectionTab"; text: "FreshBooks connection"; Layout.alignment: Qt.AlignBottom; selected: panel.s.connectionSection; onClicked: backend.connectionSection(true) }

        Item { Layout.fillWidth: true }

        Caption { text: panel.s.connected ? (panel.s.sync.online===false ? "Offline" : "Account connected") : "Not connected"; color: panel.s.connected ? Theme.green : Theme.muted }

    }

    ColumnLayout {

        visible: !panel.s.connectionSection
        Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.bottomMargin: 4

        Layout.fillWidth: true; Layout.fillHeight: true; spacing: Theme.compact ? 4 : 12

        GridLayout {
            id: reminderSections
            Layout.fillWidth: true
            columns: width>=600 ? 2 : 1
            columnSpacing: Theme.compact ? 5 : 12
            rowSpacing: Theme.compact ? 5 : 12
        Card {
            outlined: true
            id: notificationsCard; objectName: "notificationsCard"
            Layout.fillHeight: true
            padding: Theme.compact ? 8 : 14

            Layout.fillWidth: true; Layout.preferredWidth: 360

            ColumnLayout {

                anchors.fill: parent; spacing: Theme.compact ? 2 : 5

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Notifications"; color: Theme.ink; font.pixelSize: 16; font.bold: true }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Test reminder"; onClicked: backend.testReminder() }
                }

                Caption { visible: !Theme.compact; text: "Uses this computer’s local time." }

                RowLayout {

                    Layout.fillWidth: true

                    Check { text: "Daily reminder at"; checked: !!panel.draft.reminders; onClicked: panel.change("reminders",checked) }

                    Field { id: reminderClock; objectName: "reminderClock"; Layout.preferredWidth: 75; text: panel.draft.clock || "5:00"; enabled: !!panel.draft.reminders; Accessible.name: "Reminder time"
                        property bool validTime: /^(0?[1-9]|1[0-2]):[0-5][0-9]$/.test(text.trim())
                        onEditingFinished: if(validTime) panel.change("clock",text.trim())
                        ToolTip.visible: activeFocus && !validTime
                        ToolTip.text: "Enter a time such as 5:00. The last valid time stays active."
                    }

                    Select { Layout.preferredWidth: 73; model: ["AM","PM"]; currentIndex: panel.draft.period==="AM" ? 0 : 1; enabled: !!panel.draft.reminders; onActivated: panel.change("period",currentText) }

                    Item { Layout.fillWidth: true }



                }

                RowLayout {
                    Layout.fillWidth: true; spacing: 12
                    Check { text: "Weekdays only"; checked: !!panel.draft.weekdays_only; onClicked: panel.change("weekdays_only",checked) }
                    Check { text: "Show reminder popup"; checked: !!panel.draft.reminder_popup; onClicked: panel.change("reminder_popup",checked) }
                    Item { Layout.fillWidth: true }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 9
                    Text { text: 'Popup “Remind me” timer'; color: Theme.ink; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
                    Field { objectName: "remindMeDelay"; Layout.preferredWidth: 49; text: String(panel.draft.remind_me_minutes || 15); validator: IntValidator { bottom: 1; top: 1440 } inputMethodHints: Qt.ImhDigitsOnly; Accessible.name: "Popup Remind me timer in minutes"; onEditingFinished: if(acceptableInput) panel.change("remind_me_minutes",parseInt(text,10)) }
                    Text { text: "minutes"; color: Theme.ink; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
                    Item { Layout.fillWidth: true }
                }

            }

        }

        Card {
            outlined: true
            padding: Theme.compact ? 8 : 14
            id: soundOptionsCard; objectName: "soundOptionsCard"
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 260
            Layout.preferredHeight: notificationsCard.implicitHeight
            ColumnLayout {
                anchors.fill: parent; spacing: Theme.compact ? 2 : 5
                Text { text: "Sound options"; color: Theme.ink; font.pixelSize: 16; font.bold: true }
                    Check { objectName: "popupSoundToggle"; text: "Popup sounds"; checked: !!panel.draft.popup_sound; onClicked: panel.change("popup_sound",checked) }
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: false; spacing: 7
                    Text { Layout.preferredWidth: 64; text: "Main popup"; color: Theme.ink; font.pixelSize: 12 }
                    Select {
                        Accessible.name: "Main popup sound"
                        objectName: "popupSoundChoice"; Layout.fillWidth: true; Layout.preferredWidth: 120; Layout.minimumWidth: 75
                        enabled: !!panel.draft.popup_sound
                        model: panel.draft.popup_sound_options || []
                        textRole: "name"
                        currentIndex: Math.max(0,model.findIndex(function(sound) { return sound.value===(panel.draft.popup_sound_choice || "ethereal") }))
                        onActivated: panel.change("popup_sound_choice", model[currentIndex].value)
                    }
                    AppButton { objectName: "previewPopupSound"; text: "Play"; Accessible.name: "Preview main popup sound"; implicitWidth: 52; enabled: !!panel.draft.popup_sound && soundVolume.value>0; onClicked: backend.previewSound() }
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: false; spacing: 7
                    Text { Layout.preferredWidth: 64; text: "Remind me"; color: Theme.ink; font.pixelSize: 12 }
                    Select {
                        objectName: "remindMeSoundChoice"; Accessible.name: "Remind me popup sound"
                        Layout.fillWidth: true; Layout.preferredWidth: 120; Layout.minimumWidth: 75
                        enabled: !!panel.draft.popup_sound
                        model: panel.draft.popup_sound_options || []; textRole: "name"
                        currentIndex: Math.max(0,model.findIndex(function(sound) { return sound.value===(panel.draft.remind_me_sound_choice || "ethereal") }))
                        onActivated: panel.change("remind_me_sound_choice", model[currentIndex].value)
                    }
                    AppButton { objectName: "previewRemindMeSound"; text: "Play"; implicitWidth: 52; Accessible.name: "Preview Remind me popup sound"; enabled: !!panel.draft.popup_sound && soundVolume.value>0; onClicked: backend.previewRemindMeSound() }
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: false; spacing: 7
                    Text { text: "Volume"; color: Theme.ink; font.pixelSize: 13 }
                    Slider {
                        id: soundVolume; objectName: "popupVolume"; Layout.fillWidth: true; Layout.minimumWidth: 60; Layout.preferredWidth: 120
                        from: 0; to: 100; stepSize: 5; enabled: !!panel.draft.popup_sound
                        value: panel.draft.popup_volume===undefined ? 60 : panel.draft.popup_volume
                        Accessible.name: "Popup sound volume"
                        onMoved: if(!pressed) panel.change("popup_volume",Math.round(value))
                        onPressedChanged: if(!pressed && Math.round(value)!==panel.draft.popup_volume) panel.change("popup_volume",Math.round(value))
                        background: Rectangle { x: soundVolume.leftPadding; y: soundVolume.topPadding+(soundVolume.availableHeight-height)/2; width: soundVolume.availableWidth; height: 4; radius: 2; color: Theme.line
                            Rectangle { width: soundVolume.visualPosition*parent.width; height: parent.height; radius: 2; color: soundVolume.enabled ? Theme.blue : Theme.muted }
                        }
                        handle: Rectangle { x: soundVolume.leftPadding+soundVolume.visualPosition*(soundVolume.availableWidth-width); y: soundVolume.topPadding+(soundVolume.availableHeight-height)/2; width: 16; height: 16; radius: 8; color: soundVolume.pressed ? Theme.selected : Theme.surface; border.color: soundVolume.enabled ? Theme.blue : Theme.muted; border.width: 2 }
                    }
                    Text { Layout.preferredWidth: 34; text: Math.round(soundVolume.value)+"%"; color: Theme.ink; font.pixelSize: 12; horizontalAlignment: Text.AlignRight }
                }
            }
        }
        }

        Card {
            outlined: true
            padding: Theme.compact ? 8 : 14

            Layout.fillWidth: true

            GridLayout {

                anchors.fill: parent; columns: 2; columnSpacing: 20; rowSpacing: Theme.compact ? 2 : 5

                Text { Layout.columnSpan: 2; text: "App & appearance"; color: Theme.ink; font.pixelSize: 16; font.bold: true }

                Check { text: "Start with Windows"; checked: !!panel.draft.startup; enabled: !panel.s.demo; onClicked: panel.change("startup",checked) }

                Check { text: "Always on top"; checked: !!panel.draft.always_on_top; onClicked: panel.change("always_on_top",checked) }

                Check { text: "Dock by the taskbar"; checked: !!panel.draft.docked_mode; onClicked: panel.change("docked_mode",checked) }

                Check { text: "Close button hides to tray"; checked: !!panel.draft.close_to_tray; onClicked: panel.change("close_to_tray",checked) }

                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    Caption { text: "Appearance" }
                    Select { Layout.fillWidth: true; model: ["System","Light","Dark"]; currentIndex: panel.draft.theme==="dark" ? 2 : panel.draft.theme==="light" ? 1 : 0; onActivated: panel.change("theme",currentText.toLowerCase()) }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    Caption { text: "Dropdown sorting" }
                    Select { objectName: "dropdownSorting"; Layout.fillWidth: true; model: ["Alphabetical","Recently used"]; currentIndex: panel.draft.dropdown_sort==="recent" ? 1 : 0; onActivated: panel.change("dropdown_sort",currentIndex===1 ? "recent" : "alphabetical") }
                }

            }

        }

        Item { Layout.fillHeight: true }

        RowLayout {

            Layout.fillWidth: true

            Text {
                objectName: "versionLink"
                Layout.minimumHeight: 14
                text: "FreshTray " + backend.state.version
                color: Theme.blue
                font.pixelSize: 11; font.underline: linkArea.containsMouse || activeFocus
                activeFocusOnTab: true
                Accessible.role: Accessible.Link
                Accessible.name: text + ", open GitHub repository"
                Keys.onReturnPressed: backend.openRepository()
                Keys.onSpacePressed: backend.openRepository()
                MouseArea { id: linkArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.openRepository() }
                ToolTip.visible: linkArea.containsMouse
                ToolTip.text: "Open the FreshTray GitHub repository"
            }

            Item { Layout.fillWidth: true }



        }

    }

    ColumnLayout {

        visible: panel.s.connectionSection
        Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.bottomMargin: 4

        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10

        Card {
            id: connectionCard; objectName: "connectionCard"
            outlined: true
            visible: !panel.s.connected || panel.s.sync.problems.length===0 || panel.showConnectionSetup || panel.s.authStarted

            Layout.fillWidth: true

            ColumnLayout {

                anchors.fill: parent; spacing: 10

                Text { text: "Connect your FreshBooks app"; color: Theme.ink; font.pixelSize: 16; font.bold: true }

                Text { Layout.fillWidth: true; text: "Use your own FreshBooks developer app. Its credentials and tokens are encrypted for your Windows account."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }

                ColumnLayout {
                    visible: !panel.s.authStarted
                    Layout.fillWidth: true; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true; spacing: 12
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0; spacing: 4
                            Caption { Layout.fillWidth: true; text: "Client ID" }
                            Field { id: clientId; objectName: "oauthClient"; Layout.fillWidth: true; Layout.minimumWidth: 0; text: panel.s.clientId; enabled: !panel.s.busy; Accessible.name: "FreshBooks client ID" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0; spacing: 4
                            Caption { Layout.fillWidth: true; text: "Client secret" }
                            Field { id: secret; objectName: "oauthSecret"; Layout.fillWidth: true; Layout.minimumWidth: 0; echoMode: TextInput.Password; placeholderText: "Leave blank to keep saved secret"; enabled: !panel.s.busy; Accessible.name: "FreshBooks client secret" }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        Caption { Layout.fillWidth: true; text: "Registered HTTPS redirect URI" }
                        Field { id: redirect; objectName: "oauthRedirect"; Layout.fillWidth: true; text: panel.s.redirect; enabled: !panel.s.busy; Accessible.name: "Registered redirect URI" }
                    }
                    AppButton { objectName: "oauthSignIn"; Layout.alignment: Qt.AlignLeft; text: "Open browser sign-in"; enabled: !panel.s.busy && !panel.s.demo; onClicked: { backend.beginConnect(clientId.text,secret.text,redirect.text); secret.clear() } }
                }

                ColumnLayout {

                    visible: panel.s.authStarted

                    Layout.fillWidth: true; spacing: 8

                    Text { Layout.fillWidth: true; text: "After you approve access, the browser shows a localhost error page. Copy its entire address and paste it here within 5 minutes."; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 13 }

                    Caption { text: "Complete return URL from the browser" }

                    Field { id: returned; objectName: "oauthReturned"; Layout.fillWidth: true; echoMode: TextInput.PasswordEchoOnEdit; enabled: !panel.s.busy; Accessible.name: "Complete OAuth return URL" }

                    RowLayout {

                        AppButton { objectName: "oauthBack"; text: "Back"; enabled: !panel.s.busy; onClicked: { backend.cancelConnect(); returned.clear() } }

                        AppButton { objectName: "oauthFinish"; text: "Finish connection"; primary: true; enabled: !panel.s.busy && !panel.s.demo; onClicked: { backend.finishConnect(returned.text); returned.clear() } }

                    }

                }

            }

        }

        RowLayout {

            Layout.fillWidth: true; spacing: 12
            Layout.leftMargin: connectionCard.leftPadding; Layout.rightMargin: connectionCard.rightPadding

            AppButton { objectName: "refreshAccountData"; text: "Refresh FreshBooks data"; enabled: panel.s.connected && !panel.s.busy; onClicked: backend.reloadCatalog() }

            AppButton { visible: !!panel.s.legacyPending; text: "Check pending save"; enabled: panel.s.connected && !panel.s.busy; onClicked: backend.checkPending() }

            AppButton { visible: !!panel.s.legacyPending; text: "Recovery…"; enabled: !panel.s.busy; onClicked: backend.releasePending() }

            AppButton { objectName: "backToSyncReview"; text: "Back to sync review"; visible: panel.showConnectionSetup && panel.s.sync.problems.length>0; onClicked: panel.showConnectionSetup=false }

            Item { Layout.fillWidth: true }

            AppButton { objectName: "disconnectAccount"; text: "Disconnect"; destructive: true; enabled: panel.s.connected && !panel.s.busy && !panel.s.demo; onClicked: backend.disconnect() }

        }

        ColumnLayout {
            visible: !panel.s.demo && !panel.showConnectionSetup && !panel.s.authStarted && (panel.s.sync.count>0 || panel.s.sync.online===false || panel.s.sync.message.length>0)
            Layout.fillWidth: true; spacing: 5
            Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.ink; font.pixelSize: 12
                text: panel.s.sync.online===false ? "Offline. Changes are saved securely on this PC and will sync when the connection returns." : panel.s.sync.count+" locally saved change(s) waiting to sync."
            }
            Caption { Layout.fillWidth: true; visible: panel.s.sync.message.length>0; text: panel.s.sync.message; wrapMode: Text.WordWrap }
            RowLayout {
                AppButton { text: panel.s.syncing ? "Checking…" : "Check sync status"; enabled: !panel.s.syncing && !panel.s.busy; onClicked: backend.syncNow() }
                AppButton { text: panel.showConnectionSetup ? "Hide connection setup" : "Connection setup"; visible: panel.s.sync.problems.length>0; onClicked: panel.showConnectionSetup=!panel.showConnectionSetup }
            }
            Select { id: reviewChoice; objectName: "syncReviewChoice"; Layout.fillWidth: true; visible: panel.s.sync.problems.length>0 && !panel.showConnectionSetup && !panel.s.authStarted
                model: panel.s.sync.problems.map(function(p) { return p.day+" · "+p.action+" · "+p.status+(p.note ? " · "+p.note.slice(0,36) : "") })
            }
            Text { Layout.fillWidth: true; visible: reviewChoice.visible; wrapMode: Text.WordWrap; color: Theme.ink; font.pixelSize: 12
                text: panel.s.sync.problems[reviewChoice.currentIndex] ? panel.s.sync.problems[reviewChoice.currentIndex].message : ""
            }
            AppButton { objectName: "discardSyncChange"; text: "Discard local change…"; visible: reviewChoice.visible; enabled: !panel.s.busy && !panel.s.syncing
                onClicked: if(panel.s.sync.problems[reviewChoice.currentIndex]) backend.discardQueued(panel.s.sync.problems[reviewChoice.currentIndex].id)
            }
        }

        Item { Layout.fillHeight: true }


    }

    }
}
