import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: controls
    property var timer: backend.workTimer.state
    property bool compact: false
    function duration(seconds) { let n=Math.floor(seconds); return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].map(v=>String(v).padStart(2,"0")).join(":") }
    spacing: 8
    Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: "Elapsed · "+controls.duration(controls.timer.seconds); color: Theme.ink; font.pixelSize: 15; font.weight: Font.Medium }
    Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: controls.timer.status==="idle" ? "Ready to start" : controls.timer.status==="review" ? "Ready to log" : controls.timer.status==="running" ? "Running" : "Paused"; color: controls.timer.status==="running" ? Theme.green : Theme.muted; font.pixelSize: 12 }
    Field { objectName: "timerReviewDuration"; Layout.fillWidth: true; visible: controls.timer.status==="review"; text: controls.duration(controls.timer.seconds); Accessible.name: "Reviewed duration HH:MM:SS"; onEditingFinished: backend.workTimer.duration(text); enabled: !controls.timer.saving && !controls.timer.submitted }
    RowLayout {
        Layout.alignment: Qt.AlignHCenter; spacing: 8
        AppButton { objectName: "timerPause"; visible: controls.timer.status==="running" || controls.timer.status==="paused"; text: controls.timer.status==="paused" ? "Resume" : "Pause"; enabled: !controls.timer.saving; onClicked: backend.workTimer.pause() }
        AppButton { objectName: "timerPrimary"; primary: true; text: controls.timer.saving ? "Saving…" : controls.timer.status==="idle" ? "Start timer" : controls.timer.status==="review" ? "Log time" : "Stop & review"; enabled: !backend.state.busy && !controls.timer.saving && !controls.timer.submitted && controls.timer.durationValid && (controls.timer.status!=="idle" || backend.state.catalogReady); onClicked: backend.workTimer.primary() }
    }
    AppButton { Layout.alignment: Qt.AlignHCenter; visible: controls.timer.submitted; text: "Review sync"; onClicked: backend.showSync() }
    AppButton { Layout.alignment: Qt.AlignHCenter; visible: controls.timer.status==="review"; quiet: true; text: "Discard timer"; enabled: !controls.timer.saving; onClicked: backend.workTimer.discard() }
}
