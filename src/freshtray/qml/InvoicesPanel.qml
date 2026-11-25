import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: panel
    objectName: "invoicesPanel"
    property var billing: backend.invoices
    property var s: billing.state
    property string projectQuery: ""
    property bool showImportPreview: true
    property string selectedRecord: ""
    function clientIndex(id) { return s.clients.findIndex(c=>String(c.id)===String(id)) }
    function option(key,value) { billing.importField(key,value) }
    function toggleProject(id, checked) { let ids=(s.options.projects||[]).slice(); ids=ids.filter(x=>x!==id); if(checked) ids.push(id); option("projects",ids) }
    function includes(key,checked) { let ids=(s.options.includes||[]).slice().filter(x=>x!==key); if(checked) ids.push(key); option("includes",ids) }
    ColumnLayout {
        anchors.fill: parent; spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Text { textFormat: Text.PlainText; text: panel.s.view==="edit" ? "Edit invoice" : "Invoices"; color: Theme.ink; font.pixelSize: 26; font.bold: true }
            Caption { text: panel.s.local ? "Standalone" : "FreshBooks" }
            Item { Layout.fillWidth: true }

        }
        Flow {
            Layout.fillWidth: true; spacing: 8; visible: panel.s.view==="list"
            AppButton { text: "Business & local records"; onClicked: records.open() }
        }
        Text { textFormat: Text.PlainText; objectName: "invoiceProblem"; Layout.fillWidth: true; visible: !!panel.s.problem; text: panel.s.problem; wrapMode: Text.WordWrap; color: Theme.dark ? "#ff9da7" : "#b91c34"; font.pixelSize: 13 }
        Text { textFormat: Text.PlainText; Layout.fillWidth: true; visible: !!panel.s.message; text: panel.s.message; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true; visible: !panel.s.local && panel.s.view==="list"
            AppButton { text: "Sync saved drafts"; enabled: !panel.s.busy && panel.s.pending; onClicked: syncConfirm.open() }
            Item { Layout.fillWidth: true }
            Caption { visible: panel.s.busy; text: "Working…" }
        }
        ScrollView {
            id: scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: scroll.availableWidth; spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true; visible: panel.s.view==="list"; spacing: 12
                    Loader {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: scroll.availableWidth
                        Layout.preferredHeight: item ? item.implicitHeight : 0
                        active: panel.visible && panel.s.view==="list"
                        sourceComponent: Component { InvoiceOverview { state: panel.s; billing: panel.billing } }
                    }

                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: panel.s.view==="edit"; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton { text: "Invoices"; enabled: !panel.s.busy; onClicked: billing.back() }
                        Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: panel.s.draft.number || "New invoice"; color: Theme.ink; font.pixelSize: 20; font.bold: true }
                        AppButton { text: "Save"; primary: true; enabled: panel.s.editable && !panel.s.busy; onClicked: billing.save() }
                        AppButton { text: "Preview"; enabled: !panel.s.busy; onClicked: billing.showPreview() }
                        AppButton { objectName: "invoicePayments"; text: "Payments"; enabled: !panel.s.busy && (panel.s.local || !!panel.s.draft.remote); onClicked: paymentDialog.open() }
                    }
                    Text { textFormat: Text.PlainText; Layout.fillWidth: true; visible: !panel.s.editable; color: Theme.muted; wrapMode: Text.WordWrap; text: "This invoice is read-only because of its payment or sync status. You can still preview and export it." }
                    RowLayout {
                        visible: ["sending","review","conflict"].indexOf(panel.s.draft.sync)>=0
                        Layout.fillWidth: true
                        AppButton { text: "I checked FreshBooks: retry"; onClicked: retryConfirm.open() }
                        AppButton { text: "Keep local; do not sync"; onClicked: billing.review("keep") }
                    }
                    Card {
                        Layout.fillWidth: true; fadingOutline: false; padding: panel.width<700 ? 16 : 40
                        ColumnLayout { anchors.fill: parent; spacing: 30
                            RowLayout { Layout.fillWidth: true
                                Image { Layout.preferredWidth: 190; Layout.preferredHeight: 140; visible: !!panel.s.invoiceSeller.logo; source: panel.s.invoiceSeller.logo || ""; fillMode: Image.PreserveAspectFit; horizontalAlignment: Image.AlignLeft; asynchronous: false }
                                Text { visible: !panel.s.invoiceSeller.logo; text: "INVOICE"; color: Theme.blue; font.pixelSize: 24; font.bold: true }
                                Item { Layout.fillWidth: true }
                                ColumnLayout { Layout.maximumWidth: 280
                                    Text { Layout.fillWidth: true; text: panel.s.invoiceSeller.name || "Your business"; textFormat: Text.PlainText; color: Theme.ink; font.bold: true; horizontalAlignment: Text.AlignRight; wrapMode: Text.WordWrap }
                                    Caption { Layout.fillWidth: true; text: panel.s.invoiceSeller.address || ""; horizontalAlignment: Text.AlignRight; wrapMode: Text.WordWrap }
                                    Caption { Layout.fillWidth: true; text: panel.s.invoiceSeller.phone || ""; horizontalAlignment: Text.AlignRight }
                                    Caption { Layout.fillWidth: true; text: panel.s.invoiceSeller.email || ""; horizontalAlignment: Text.AlignRight }
                                    AppButton { Layout.alignment: Qt.AlignRight; quiet: true; text: "Edit business information"; onClicked: records.open() }
                                }
                            }
                            Item { implicitHeight: 12 }
                    Card {
                        outlined: false
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent; spacing: 10
                            GridLayout {
                                Layout.fillWidth: true; columns: panel.width<700 ? 2 : 4; columnSpacing: 16; rowSpacing: 12
                                ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.fillWidth: true; Layout.minimumWidth: 0
                                    Caption { text: "Billed To" }
                                    Select { objectName: "invoiceClient"; Layout.fillWidth: true; model: panel.s.clients; textRole: "name"; currentIndex: panel.clientIndex(panel.s.draft.client); enabled: panel.s.editable && !panel.s.busy; onActivated: billing.field("client",String(model[currentIndex].id)) }
                                    Caption { Layout.fillWidth: true; text: { let c=panel.s.clients[panel.clientIndex(panel.s.draft.client)]; return c ? (c.address || "") : "" } wrapMode: Text.WordWrap }
                                }
                                ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.fillWidth: true; Layout.minimumWidth: 0
                                    Caption { text: "Date of Issue" }
                                    Field { Layout.fillWidth: true; text: panel.s.draft.date; placeholderText: "YYYY-MM-DD"; enabled: panel.s.editable; onTextEdited: billing.field("date",text) }
                                    Caption { text: "Due Date" }
                                    Field { Layout.fillWidth: true; text: panel.s.draft.due; placeholderText: "YYYY-MM-DD"; enabled: panel.s.editable; onTextEdited: billing.field("due",text) }
                                }
                                ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.fillWidth: true; Layout.minimumWidth: 0
                                    Caption { text: "Invoice Number" }
                                    Field { Layout.fillWidth: true; text: panel.s.draft.number; placeholderText: "Assign on save"; enabled: panel.s.editable; onTextEdited: billing.field("number",text) }
                                    Caption { text: "Purchase Order" }
                                    Field { Layout.fillWidth: true; text: panel.s.draft.po; enabled: panel.s.editable; onTextEdited: billing.field("po",text) }
                                }
                                ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.fillWidth: true; Layout.minimumWidth: 0
                                    Caption { text: "Amount Due" }
                                    Text { Layout.fillWidth: true; text: panel.s.totals.balance; color: Theme.ink; font.pixelSize: 36; elide: Text.ElideRight }
                                    Caption { text: "Currency" }
                                    Field { Layout.fillWidth: true; text: panel.s.draft.currency; enabled: panel.s.editable && !panel.s.draft.remote; maximumLength: 3; onTextEdited: billing.field("currency",text.toUpperCase()) }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Select { Layout.fillWidth: true; model: [{id:"",name:"Choose a saved item"}].concat(panel.s.items); textRole: "name"; enabled: panel.s.editable; onActivated: if(currentIndex>0) { billing.pickItem(String(model[currentIndex].id)); currentIndex=0 } }
                        AppButton { text: "Import unbilled entries"; enabled: panel.s.editable && !!panel.s.draft.client && !panel.s.busy; onClicked: billing.openImport() }
                    }
                    Repeater {
                        model: panel.visible && panel.s.view==="edit" ? panel.s.draft.lines.length : 0
                        delegate: Card {
                            outlined: false
                            id: lineCard
                            required property int index
                            readonly property var modelData: panel.s.draft.lines[index] || ({})
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 7
                                GridLayout {
                                    Layout.fillWidth: true; columns: panel.width<700 ? 2 : 5; columnSpacing: 16; rowSpacing: 12
                                    ColumnLayout { Layout.fillWidth: true; Layout.preferredWidth: 540; Layout.minimumWidth: 0
                                        Caption { text: "Description"; visible: lineCard.index===0 }
                                        Field { Layout.fillWidth: true; text: lineCard.modelData.name; placeholderText: "Item or service"; enabled: panel.s.editable; onTextEdited: billing.line(lineCard.index,"name",text) }
                                        TextArea { Layout.fillWidth: true; Layout.minimumWidth: 0; implicitHeight: Math.max(64,contentHeight+16); text: lineCard.modelData.description; placeholderText: "Add a description"; enabled: panel.s.editable; color: Theme.ink; font.pixelSize: 13; wrapMode: TextEdit.Wrap; selectByMouse: true; background: Rectangle { color: Theme.surface; radius: 4; border.color: parent.activeFocus ? Theme.blue : "transparent" } onTextChanged: if(activeFocus && text!==lineCard.modelData.description) billing.line(lineCard.index,"description",text) }
                                    }
                                    ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.preferredWidth: 100; Layout.minimumWidth: 0; Layout.fillWidth: true; Caption { text: "Rate" } Field { Layout.fillWidth: true; text: String(lineCard.modelData.rate); enabled: panel.s.editable; onTextEdited: billing.line(lineCard.index,"rate",text) } }
                                    ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.preferredWidth: 70; Layout.minimumWidth: 0; Layout.fillWidth: true; Caption { text: "Qty / hours" } Field { Layout.fillWidth: true; text: String(lineCard.modelData.qty); enabled: panel.s.editable; onTextEdited: billing.line(lineCard.index,"qty",text) } }
                                    ColumnLayout { Layout.alignment: Qt.AlignTop; Layout.preferredWidth: 100; Layout.minimumWidth: 0; Layout.fillWidth: true; Caption { text: "Line Total" } Text { Layout.fillWidth: true; text: lineCard.modelData.amount; color: Theme.ink; font.bold: true; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight } Caption { text: "Tax (%)" } Field { Layout.fillWidth: true; text: String(lineCard.modelData.tax); enabled: panel.s.editable; onTextEdited: billing.line(lineCard.index,"tax",text) } }
                                    AppButton { glyph: "close"; Accessible.name: "Remove invoice line"; enabled: panel.s.editable && panel.s.draft.lines.length>1; onClicked: billing.removeLine(lineCard.index) }
                                }
                                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
                                Caption { visible: false; text: "Linked imported entries" }
                            }
                        }
                    }
                    AppButton { text: "Add line"; enabled: panel.s.editable; onClicked: billing.addLine() }
                    Card {
                        outlined: false
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent; spacing: 8
                            Caption { text: "Discount (%)" }
                            Field { Layout.fillWidth: true; text: panel.s.draft.discount; enabled: panel.s.editable; onTextEdited: billing.field("discount",text) }
                            Caption { text: "Client note" }
                            TextArea { Layout.fillWidth: true; implicitHeight: 80; text: panel.s.draft.note; enabled: panel.s.editable; color: Theme.ink; wrapMode: TextEdit.Wrap; background: Rectangle { color: Theme.surface; radius: 5; border.color: Theme.line } onTextChanged: if(activeFocus && text!==panel.s.draft.note) billing.field("note",text) }
                            Caption { text: "Payment terms" }
                            Field { Layout.fillWidth: true; text: panel.s.draft.terms; enabled: panel.s.editable; onTextEdited: billing.field("terms",text) }
                            Text { textFormat: Text.PlainText; text: "Subtotal "+panel.s.totals.subtotal+"  − Discount "+panel.s.totals.discount+"  + Tax "+panel.s.totals.tax; color: Theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text { textFormat: Text.PlainText; text: "Total: "+panel.s.totals.total+" "+panel.s.draft.currency; color: Theme.blue; font.pixelSize: 21; font.bold: true }
                        }
                    }
                        }
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 8
                        AppButton { objectName: "invoiceSave"; text: "Save invoice"; primary: true; enabled: panel.s.editable && !panel.s.busy; onClicked: billing.save() }
                        AppButton { objectName: "invoicePreview"; text: "Preview"; enabled: !panel.s.busy; onClicked: billing.showPreview() }
                        AppButton { text: "Export PDF"; enabled: !panel.s.busy; onClicked: billing.exportPdf() }
                        AppButton { text: "Email draft"; enabled: !panel.s.busy; onClicked: billing.emailDraft() }
                        AppButton { text: "Email file with PDF"; enabled: !panel.s.busy; onClicked: billing.exportEmail() }
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 8; visible: panel.s.local
                        AppButton { text: "Mark sent (local)"; enabled: !panel.s.busy && panel.s.draft.status==="Draft"; onClicked: billing.localAction("sent","") }
                        AppButton { text: "Archive invoice"; enabled: !panel.s.busy; onClicked: archiveConfirm.open() }
                    }
                    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Email draft opens your default mail app. Attach your exported PDF and select your sending account there. Email files include the attachment; mail-app support varies. Nothing is sent automatically." }
                }
                ColumnLayout {
                    visible: panel.s.view==="preview"; Layout.fillWidth: true; spacing: 12
                    RowLayout {
                        AppButton { text: "Back to editing"; onClicked: billing.editPreview() }
                        AppButton { text: "Export PDF"; onClicked: billing.exportPdf() }
                        AppButton { text: "Email draft"; onClicked: billing.emailDraft() }
                        AppButton { text: "Email file with PDF"; onClicked: billing.exportEmail() }
                    }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: previewText.implicitHeight+40; color: "white"; radius: 8; border.color: Theme.line
                        Text { id: previewText; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 20; text: panel.visible && panel.s.view==="preview" ? panel.s.preview : ""; textFormat: Text.RichText; wrapMode: Text.WordWrap; color: "#062b54" }
                    }
                }
                ColumnLayout {
                    visible: panel.s.view==="import"; Layout.fillWidth: true; spacing: 12
                    RowLayout { Layout.fillWidth: true; Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: "Review unbilled time & expenses"; wrapMode: Text.WordWrap; color: Theme.ink; font.pixelSize: 21; font.bold: true } AppButton { text: "Cancel"; onClicked: billing.editPreview() } }
                    Select { Layout.fillWidth: true; model: ["All time","This month","Last month","Custom"]; currentIndex: ["all","month","last","custom"].indexOf(panel.s.options.range || "all"); onActivated: { option("range",["all","month","last","custom"][currentIndex]); let now=new Date(); let start="",end=""; if(currentIndex===1 || currentIndex===2) { let m=now.getMonth()-(currentIndex===2?1:0); start=Qt.formatDate(new Date(now.getFullYear(),m,1),"yyyy-MM-dd"); end=Qt.formatDate(new Date(now.getFullYear(),m+1,0),"yyyy-MM-dd") } option("from",start); option("to",end) } }
                    RowLayout {
                        Layout.fillWidth: true
                        Field { Layout.fillWidth: true; placeholderText: "From · YYYY-MM-DD (blank = all)"; text: panel.s.options.from || ""; onTextEdited: option("from",text) }
                        Field { Layout.fillWidth: true; placeholderText: "Through · YYYY-MM-DD"; text: panel.s.options.to || ""; onTextEdited: option("to",text) }
                    }
                    Field { Layout.fillWidth: true; placeholderText: "Find a project"; onTextEdited: panel.projectQuery=text.toLowerCase() }
                    Check { text: "Select all projects"; checked: panel.s.projects.length>0 && (panel.s.options.projects||[]).length===panel.s.projects.length; onClicked: option("projects",checked?panel.s.projects.map(p=>p.id):[]) }
                    Repeater {
                        model: panel.visible && panel.s.view==="import" ? panel.s.projects : []
                        delegate: Check { required property var modelData; visible: modelData.name.toLowerCase().indexOf(panel.projectQuery)>=0; text: modelData.name+" · "+modelData.hours+" hours"; checked: modelData.selected; onClicked: panel.toggleProject(modelData.id,checked) }
                    }
                    Caption { text: "Expenses" }
                    Select { Layout.fillWidth: true; model: ["All unbilled expenses for this client","Only expenses for selected projects","No expenses"]; currentIndex: ["all","selected","none"].indexOf(panel.s.options.expenses || "all"); onActivated: option("expenses",["all","selected","none"][currentIndex]) }
                    Caption { text: "Bulk hourly rate · expenses are unchanged" }
                    RowLayout {
                        Layout.fillWidth: true
                        Field { id: bulkRate; objectName: "invoiceBulkRate"; Layout.fillWidth: true; placeholderText: "Use existing rates (may be zero)"; text: panel.s.options.rate || "" }
                        AppButton { text: "Apply to all hours"; onClicked: option("rate",bulkRate.text) }
                        AppButton { text: "Original rates"; onClicked: { bulkRate.clear(); option("rate","") } }
                    }
                    Caption { text: panel.s.options.rate!==undefined && panel.s.options.rate!=="" ? "Applied rate: "+panel.s.options.rate+" / hour" : "Review rates before adding, especially unassigned time." }
                    RowLayout {
                        Layout.fillWidth: true
                        Select { Layout.fillWidth: true; model: ["Detailed","Grouped","Simple"]; currentIndex: ["detailed","grouped","simple"].indexOf(panel.s.options.format || "detailed"); onActivated: option("format",["detailed","grouped","simple"][currentIndex]) }
                        Select { visible: panel.s.options.format==="grouped"; Layout.fillWidth: true; model: ["Service","Team member","Day"]; currentIndex: ["service","member","date"].indexOf(panel.s.options.group || "service"); onActivated: option("group",["service","member","date"][currentIndex]) }
                    }
                    Caption { text: "Include in description" }
                    Flow {
                        Layout.fillWidth: true; spacing: 10
                        Repeater { model: ["service","project","member","date","notes","hours"]; delegate: Check { required property string modelData; text: modelData==="member"?"Team member":modelData; checked: (panel.s.options.includes||[]).indexOf(modelData)>=0; onClicked: panel.includes(modelData,checked) } }
                    }
                    Check { text: "Show preview"; checked: panel.showImportPreview; onClicked: panel.showImportPreview=checked }
                    Repeater {
                        model: panel.visible && panel.s.view==="import" && panel.showImportPreview ? panel.s.importLines : []
                        delegate: Card { required property var modelData; Layout.fillWidth: true
                            ColumnLayout { anchors.fill: parent; spacing: 4; Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: modelData.name+" · "+modelData.qty+" × "+modelData.rate+" = "+modelData.amount; color: Theme.ink; wrapMode: Text.WordWrap } Caption { Layout.fillWidth: true; text: modelData.description; wrapMode: Text.WordWrap } }
                        }
                    }
                    Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: panel.s.importLines.length+" lines · "+panel.s.importLines.reduce((sum,l)=>sum+Number(l.amount||0),0).toFixed(2)+" "+panel.s.draft.currency+" before invoice tax/discount"; color: Theme.ink; font.bold: true }
                    AppButton { text: "Add to invoice"; primary: true; enabled: !panel.s.busy && panel.s.importLines.length>0 && !panel.s.problem; onClicked: billing.addImport() }
                }
            }
        }
    }
    Dialog {
        id: records; objectName: "localRecordsDialog"; parent: Overlay.overlay; modal: true; width: Math.min(600,parent.width-24); height: Math.min(590,parent.height-24); x: (parent.width-width)/2; y: (parent.height-height)/2; padding: 16
        background: Rectangle { color: Theme.surface; radius: 9; border.color: Theme.line }
        header: Text { textFormat: Text.PlainText; text: "Business & local records"; padding: 16; color: Theme.ink; font.pixelSize: 19; font.bold: true }
        onOpened: { panel.selectedRecord=""; recordType.currentIndex=0; recordName.text=panel.s.seller.name; recordEmail.text=panel.s.seller.email; recordAddress.text=panel.s.seller.address; recordRate.text="0.00" }
        contentItem: ScrollView { clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: parent.width; spacing: 10
                Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: panel.s.problem || panel.s.message; color: Theme.muted; wrapMode: Text.WordWrap }
                Select { id: recordType; Layout.fillWidth: true; model: panel.s.local ? ["Business details","Client","Project","Expense","Saved item"] : ["Business details"]; onActivated: { panel.selectedRecord=""; if(currentIndex===0) { recordName.text=panel.s.seller.name; recordEmail.text=panel.s.seller.email; recordAddress.text=panel.s.seller.address } else { recordName.clear(); recordEmail.clear(); recordAddress.clear() } } }
                Select {
                    Layout.fillWidth: true; visible: recordType.currentIndex>0
                    model: [{id:"",name:"Add new record"}].concat(panel.s.records[["","clients","projects","expenses","items"][recordType.currentIndex]]||[]); textRole: "name"
                    onActivated: { let row=model[currentIndex]; panel.selectedRecord=String(row.id); recordName.text=row.name||""; recordEmail.text=row.email||""; recordAddress.text=row.address||""; recordRate.text=String(row.rate||row.amount||"0.00"); if(row.date) recordDate.text=row.date; recordClient.currentIndex=panel.clientIndex(row.client_id); Qt.callLater(function(){ recordProject.currentIndex=Math.max(0,recordProject.model.findIndex(p=>String(p.id)===String(row.project_id||""))) }) }
                }
                Caption { text: "Name" }
                Field { id: recordName; objectName: "localRecordName"; Layout.fillWidth: true; text: panel.s.seller.name }
                Caption { visible: recordType.currentIndex<=1; text: "Email" }
                Field { id: recordEmail; Layout.fillWidth: true; visible: recordType.currentIndex<=1; text: panel.s.seller.email }
                Caption { visible: recordType.currentIndex<=1; text: "Address" }
                Field { id: recordAddress; Layout.fillWidth: true; visible: recordType.currentIndex<=1; text: panel.s.seller.address }
                Caption { visible: recordType.currentIndex===0; text: "Default currency" }
                ColumnLayout { visible: recordType.currentIndex===0; Layout.fillWidth: true
                    Caption { text: "Business logo" }
                    Image { visible: !!panel.s.seller.logo; source: panel.s.seller.logo || ""; Layout.preferredWidth: 180; Layout.preferredHeight: 90; fillMode: Image.PreserveAspectFit; horizontalAlignment: Image.AlignLeft }
                    RowLayout {
                        AppButton { text: panel.s.seller.logo ? "Change logo" : "Choose logo"; enabled: !panel.s.busy; onClicked: billing.chooseLogo() }
                        AppButton { text: "Remove logo"; visible: !!panel.s.seller.logo; enabled: !panel.s.busy; onClicked: billing.removeLogo() }
                    }
                    Caption { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "PNG or JPEG. Saved locally and embedded in invoice PDFs. Previously saved invoices retain their branding unless you change the logo while editing them." }
                }
                Field { id: recordCurrency; Layout.fillWidth: true; visible: recordType.currentIndex===0; text: panel.s.seller.currency; maximumLength: 3 }
                Caption { visible: recordType.currentIndex===2 || recordType.currentIndex===3; text: "Client" }
                Select { id: recordClient; Layout.fillWidth: true; visible: recordType.currentIndex===2 || recordType.currentIndex===3; model: panel.s.clients; textRole: "name" }
                Select { id: recordProject; Layout.fillWidth: true; visible: recordType.currentIndex===3; model: [{id:"",name:"No project"}].concat((panel.s.records.projects||[]).filter(p=>recordClient.currentIndex>=0 && String(p.client_id)===String(recordClient.model[recordClient.currentIndex].id))); textRole: "name" }
                Caption { visible: recordType.currentIndex===3; text: "Expense date · YYYY-MM-DD" }
                Field { id: recordDate; Layout.fillWidth: true; visible: recordType.currentIndex===3; text: Qt.formatDate(new Date(),"yyyy-MM-dd") }
                Caption { visible: recordType.currentIndex===3 || recordType.currentIndex===4; text: recordType.currentIndex===3 ? "Expense amount" : "Item rate" }
                Field { id: recordRate; Layout.fillWidth: true; visible: recordType.currentIndex>=3; text: "0.00" }
                Caption { visible: recordType.currentIndex===3; text: "Expenses without a project are included by All expenses or No project."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                AppButton { text: "Save record"; primary: true; enabled: !panel.s.busy && !backend.state.busy; onClicked: {
                    let k=recordType.currentIndex
                    if(k===0) billing.seller({name:recordName.text,email:recordEmail.text,address:recordAddress.text,currency:recordCurrency.text})
                    else billing.addRecord(["","clients","projects","expenses","items"][k],{id:panel.selectedRecord,name:recordName.text,email:recordEmail.text,address:recordAddress.text,client_id:recordClient.currentIndex>=0?String(recordClient.model[recordClient.currentIndex].id):"",date:recordDate.text,amount:recordRate.text,rate:recordRate.text,project_id:recordProject.currentIndex>0?String(recordProject.model[recordProject.currentIndex].id):""})
                } }
            }
        }
        footer: AppButton { text: "Done"; onClicked: records.close() }
    }
    PaymentDialog { id: paymentDialog; tools: billing.billingTools; invoice: panel.s }
    Dialog {
        id: archiveConfirm; implicitHeight: 230; parent: Overlay.overlay; modal: true; title: "Archive local invoice?"; standardButtons: Dialog.Ok|Dialog.Cancel
        x: (parent.width-width)/2; y: (parent.height-height)/2; width: Math.min(430,parent.width-30)
        contentItem: Text { text: "The invoice is retained in encrypted storage but hidden from the list. Its imported entries become available to invoice again. No FreshBooks record is changed."; color: Theme.ink; wrapMode: Text.WordWrap }
        onAccepted: billing.localAction("archive","")
    }
    Dialog {
        id: syncConfirm; implicitHeight: 230; parent: Overlay.overlay; modal: true; title: "Sync invoice drafts?"; standardButtons: Dialog.Ok|Dialog.Cancel
        x: (parent.width-width)/2; y: (parent.height-height)/2; width: Math.min(450,parent.width-30)
        Text { textFormat: Text.PlainText; width: parent.width; text: "This creates or updates saved draft invoices in FreshBooks. Imported time and expenses may become billed there. It does not email clients. Review the draft before continuing."; color: Theme.ink; wrapMode: Text.WordWrap }
        onAccepted: billing.sync()
    }
    Dialog {
        id: retryConfirm; implicitHeight: 230; parent: Overlay.overlay; modal: true; title: "Retry after review?"; standardButtons: Dialog.Ok|Dialog.Cancel
        x: (parent.width-width)/2; y: (parent.height-height)/2; width: Math.min(450,parent.width-30)
        Text { textFormat: Text.PlainText; width: parent.width; text: "Check FreshBooks first. If the invoice already exists, do not retry: that could create a duplicate. Continue only after confirming the previous change was not applied."; wrapMode: Text.WordWrap; color: Theme.ink }
        onAccepted: billing.review("retry")
    }
}
