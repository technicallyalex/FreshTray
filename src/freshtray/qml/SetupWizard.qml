import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: wizard
    objectName: "setupWizard"
    modal: true
    property int step: 0
    function advance(value) { backend.traceWizardOpening(); Qt.callLater(function() { wizard.step=value }) }
    width: Math.min(650, parent ? parent.width-24 : 650)
    height: Math.min(620, parent ? parent.height-24 : 620)
    x: parent ? (parent.width-width)/2 : 0
    y: parent ? (parent.height-height)/2 : 0
    padding: 18
    background: Rectangle { radius: 10; color: Theme.surface; border.color: Theme.line }
    header: Text { text: "FreshTray setup"; padding: 18; color: Theme.ink; font.pixelSize: 21; font.bold: true }
    onAboutToShow: { step=0; stepLoader.active=true }
    onAboutToHide: if(stepLoader.item && typeof stepLoader.item.clearSensitive==="function") stepLoader.item.clearSensitive()
    onClosed: { stepLoader.active=false; if(backend.state.authStarted && !backend.state.busy) backend.cancelConnect() }
    contentItem: ScrollView {
        id: setupScroll
        clip: true; contentWidth: availableWidth; contentHeight: setupContent.implicitHeight
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ColumnLayout {
            id: setupContent
            width: setupScroll.availableWidth; spacing: 14
            Caption { text: "Step "+(wizard.step+1)+" of 4" }
            Text { Layout.fillWidth: true; color: Theme.ink; font.pixelSize: 18; font.bold: true; wrapMode: Text.WordWrap; text: ["Create your FreshBooks app", "Grant the right permissions", "Connect your account", "Finish and verify"][wizard.step] }
            Loader {
                id: stepLoader
                active: false
                Layout.fillWidth: true; Layout.minimumWidth: 0
                Layout.preferredHeight: item ? item.implicitHeight : 0
                sourceComponent: [developerPage,permissionsPage,connectionPage,finishPage][wizard.step]
            }
        }
    }
    footer: Item {
        implicitHeight: 58
        RowLayout { anchors.fill: parent; anchors.margins: 12; spacing: 10
            AppButton { text: "Close"; onClicked: wizard.close() }
            Item { Layout.fillWidth: true }
            AppButton { text: "Back"; visible: wizard.step>0; enabled: !backend.state.busy; onClicked: wizard.advance(wizard.step-1) }
            AppButton { text: "Next"; visible: wizard.step<3; enabled: !backend.state.busy; onClicked: wizard.advance(wizard.step+1) }
        }
    }
    Component { id: developerPage
            ColumnLayout {
                implicitWidth: 0; spacing: 12
                Text { Layout.fillWidth: true; color: Theme.ink; wrapMode: Text.WordWrap; text: "1. Sign in to FreshBooks and open the developer page.\n2. Create an app named FreshTray.\n3. Add this exact redirect URI and save your app settings." }
                AppButton { text: "Open FreshBooks developer page"; onClicked: backend.openDeveloperPortal() }
                Field { Layout.fillWidth: true; text: "https://localhost:8765/callback"; readOnly: true; Accessible.name: "Registered HTTPS redirect URI" }
                AppButton { text: "Copy redirect URI"; onClicked: backend.copySetup("redirect") }
                Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Keep the client secret private. FreshTray encrypts saved credentials for your Windows account." }
            }
    }
    Component { id: permissionsPage
            ColumnLayout {
                implicitWidth: 0; spacing: 12
                Text { Layout.fillWidth: true; color: Theme.ink; wrapMode: Text.WordWrap; text: "Add these scopes in your developer app:\n\nuser:profile:read\nuser:clients:read\nuser:projects:read\nuser:billable_items:read\nuser:time_entries:read\nuser:time_entries:write\nuser:invoices:read\nuser:invoices:write\nuser:expenses:read\nuser:business:read\nuser:uploads:read\nuser:clients:write\nuser:estimates:read\nuser:estimates:write\nuser:payments:read\nuser:payments:write" }
                AppButton { text: "Copy scope list"; onClicked: backend.copySetup("scopes") }
                Text { Layout.fillWidth: true; color: Theme.muted; wrapMode: Text.WordWrap; text: "Save the developer app settings. If FreshBooks still denies access after a permission change, revoke the previous authorization in FreshBooks, then sign in again." }
            }
    }
    Component { id: connectionPage
            ColumnLayout {
                implicitWidth: 0; spacing: 8
                function clearSensitive() { setupSecret.clear(); setupReturned.clear() }
                Component.onCompleted: { setupId.text=backend.state.clientId; setupRedirect.text=backend.state.redirect }
                Caption { text: "Client ID" }
                Field { id: setupId; objectName: "setupClientId"; Layout.fillWidth: true; enabled: !backend.state.authStarted && !backend.state.busy }
                Caption { text: "Client secret · blank keeps your saved secret" }
                Field { id: setupSecret; objectName: "setupClientSecret"; Layout.fillWidth: true; echoMode: TextInput.Password; enabled: !backend.state.authStarted && !backend.state.busy }
                Caption { text: "Registered HTTPS redirect URI" }
                Field { id: setupRedirect; Layout.fillWidth: true; text: "https://localhost:8765/callback"; enabled: !backend.state.authStarted && !backend.state.busy }
                AppButton { text: "Open secure sign-in"; enabled: !backend.state.busy && !backend.state.authStarted; onClicked: { backend.beginBillingConnect(setupId.text,setupSecret.text,setupRedirect.text); setupSecret.clear() } }
                Text { Layout.fillWidth: true; visible: backend.state.authStarted; color: Theme.muted; wrapMode: Text.WordWrap; text: "Approve access in your browser. The localhost error page is expected: copy the entire browser address and paste it below within five minutes." }
                Field { id: setupReturned; objectName: "setupReturnUrl"; Layout.fillWidth: true; visible: backend.state.authStarted; echoMode: TextInput.Password; placeholderText: "Complete return URL from browser" }
                RowLayout {
                    visible: backend.state.authStarted
                    AppButton { text: "Start over"; enabled: !backend.state.busy; onClicked: { backend.cancelConnect(); setupReturned.clear() } }
                    AppButton { text: "Finish connection"; primary: true; enabled: !backend.state.busy; onClicked: { backend.finishConnect(setupReturned.text); setupReturned.clear() } }
                }
            }
    }
    Component { id: finishPage
            ColumnLayout {
                implicitWidth: 0; spacing: 12
                Text { Layout.fillWidth: true; color: Theme.ink; wrapMode: Text.WordWrap; text: backend.state.localMode ? "Add your business details and a client to begin." : "Choose your business in Log time. Return to FreshBooks connection and refresh the saved records you need." }
                AppButton {
                    text: backend.state.localMode ? "Open invoices" : "Open connection settings"
                    primary: true
                    onClicked: {
                        backend.selectPanel(backend.state.localMode ? "invoices" : "settings")
                        if (!backend.state.localMode) backend.connectionSection(true)
                        wizard.close()
                    }
                }
                Text { Layout.fillWidth: true; color: Theme.muted; wrapMode: Text.WordWrap; text: "PDF export works locally. Email draft uses your default mail app; attach the PDF yourself. Email file (.eml) includes the PDF, but opening it as an editable draft depends on your mail app. Nothing is sent automatically." }
            }
    }
}
