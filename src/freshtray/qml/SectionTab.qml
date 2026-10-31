import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property bool selected: false
    implicitWidth: label.implicitWidth+28
    implicitHeight: Theme.compact ? (selected ? 30 : 27) : (selected ? 35 : 31)
    Accessible.role: Accessible.PageTab
    Accessible.name: text
    contentItem: Text {
        id: label
        text: control.text; color: control.selected ? Theme.blue : Theme.muted
        font.pixelSize: 13; font.bold: control.selected; font.underline: false
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Canvas {
        id: shape
        property color fillColor: control.selected ? Theme.surface : control.hovered ? Theme.hover : Theme.page
        property color lineColor: Theme.line
        property color foldColor: Theme.hover
        onFillColorChanged: requestPaint()
        onLineColorChanged: requestPaint()
        onFoldColorChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: control; function onSelectedChanged() { shape.requestPaint() } }
        onPaint: {
            const c=getContext("2d"); c.reset()
            const fold=6
            c.beginPath(); c.moveTo(.5,height); c.lineTo(.5,5)
            c.quadraticCurveTo(.5,.5,5,.5); c.lineTo(width-fold,.5)
            c.lineTo(width-.5,fold); c.lineTo(width-.5,height)
            c.fillStyle=fillColor; c.fill()
            if(!control.selected) c.lineTo(.5,height-.5)
            c.strokeStyle=lineColor; c.lineWidth=1; c.stroke()
            c.beginPath(); c.moveTo(width-fold,.5)
            c.lineTo(width-fold,fold); c.lineTo(width-.5,fold)
            c.closePath(); c.fillStyle=foldColor; c.fill()
            c.strokeStyle=lineColor; c.stroke()
        }
    }
    Rectangle { visible: control.selected; x: 1; y: parent.height-1; width: parent.width-2; height: 3; color: Theme.surface }
}
