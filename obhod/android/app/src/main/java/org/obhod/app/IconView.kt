package org.obhod.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View
import kotlin.math.cos
import kotlin.math.sin

/** Простые линейные иконки без библиотек: рисуются в квадрате 24×24, как Material Symbols. */
class IconView(context: Context, private val kind: Kind, color: Int) : View(context) {
    enum class Kind { POWER, ROUTE, GEAR, GLOBE, SWAP, TUNE, LAYERS, LOG, BATTERY, SHIELD, INFO, KEY, PASTE, TRASH, BACK }

    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
        this.color = color
    }

    var color: Int
        get() = p.color
        set(v) { p.color = v; invalidate() }

    override fun onDraw(c: Canvas) {
        val s = minOf(width, height) / 24f
        c.save()
        c.translate((width - 24 * s) / 2, (height - 24 * s) / 2)
        c.scale(s, s)
        p.strokeWidth = 2f
        when (kind) {
            Kind.POWER -> {
                c.drawArc(RectF(4f, 5f, 20f, 21f), -60f, 300f, false, p)
                c.drawLine(12f, 2.5f, 12f, 11f, p)
            }
            Kind.ROUTE -> {
                c.drawCircle(6f, 19f, 2.5f, p)
                c.drawCircle(18f, 5f, 2.5f, p)
                c.drawPath(Path().apply {
                    moveTo(8.5f, 19f); lineTo(15f, 19f); cubicTo(19f, 19f, 19f, 12f, 15f, 12f)
                    lineTo(9f, 12f); cubicTo(5f, 12f, 5f, 5f, 9f, 5f); lineTo(15.5f, 5f)
                }, p)
            }
            Kind.GEAR -> {
                c.drawCircle(12f, 12f, 3f, p)
                val path = Path()
                for (i in 0 until 8) {
                    val a = Math.toRadians(i * 45.0)
                    path.moveTo(12 + 7 * cos(a).toFloat(), 12 + 7 * sin(a).toFloat())
                    path.lineTo(12 + 9.5f * cos(a).toFloat(), 12 + 9.5f * sin(a).toFloat())
                }
                c.drawPath(path, p)
                c.drawCircle(12f, 12f, 7f, p)
            }
            Kind.GLOBE -> {
                c.drawCircle(12f, 12f, 9f, p)
                c.drawOval(RectF(8f, 3f, 16f, 21f), p)
                c.drawLine(3f, 12f, 21f, 12f, p)
            }
            Kind.SWAP -> {
                c.drawPath(Path().apply { moveTo(4f, 8f); lineTo(20f, 8f); moveTo(16f, 4f); lineTo(20f, 8f); lineTo(16f, 12f) }, p)
                c.drawPath(Path().apply { moveTo(20f, 16f); lineTo(4f, 16f); moveTo(8f, 12f); lineTo(4f, 16f); lineTo(8f, 20f) }, p)
            }
            Kind.TUNE -> {
                for ((y, x) in listOf(6f to 8f, 12f to 16f, 18f to 10f)) {
                    c.drawLine(3f, y, 21f, y, p)
                    c.drawCircle(x, y, 2.2f, p.apply { style = Paint.Style.FILL })
                    p.style = Paint.Style.STROKE
                }
            }
            Kind.LAYERS -> {
                c.drawPath(Path().apply { moveTo(12f, 3f); lineTo(21f, 8f); lineTo(12f, 13f); lineTo(3f, 8f); close() }, p)
                c.drawPath(Path().apply { moveTo(3f, 12.5f); lineTo(12f, 17.5f); lineTo(21f, 12.5f) }, p)
                c.drawPath(Path().apply { moveTo(3f, 17f); lineTo(12f, 22f); lineTo(21f, 17f) }, p)
            }
            Kind.LOG -> {
                c.drawRoundRect(RectF(5f, 3f, 19f, 21f), 2f, 2f, p)
                for (y in listOf(8f, 12f, 16f)) c.drawLine(8f, y, 16f, y, p)
            }
            Kind.BATTERY -> {
                c.drawRoundRect(RectF(7f, 5f, 17f, 21f), 2f, 2f, p)
                c.drawLine(10f, 3f, 14f, 3f, p)
                c.drawPath(Path().apply { moveTo(13f, 9f); lineTo(10.5f, 13f); lineTo(13.5f, 13f); lineTo(11f, 17f) }, p)
            }
            Kind.SHIELD -> c.drawPath(Path().apply {
                moveTo(12f, 3f); lineTo(19f, 6f); lineTo(19f, 11f); cubicTo(19f, 16f, 15.5f, 19.5f, 12f, 21f)
                cubicTo(8.5f, 19.5f, 5f, 16f, 5f, 11f); lineTo(5f, 6f); close()
            }, p)
            Kind.INFO -> {
                c.drawCircle(12f, 12f, 9f, p)
                c.drawLine(12f, 11f, 12f, 16.5f, p)
                c.drawPoint(12f, 7.5f, p.apply { strokeWidth = 2.6f })
            }
            Kind.KEY -> {
                c.drawCircle(8f, 12f, 4f, p)
                c.drawPath(Path().apply { moveTo(12f, 12f); lineTo(21f, 12f); moveTo(18f, 12f); lineTo(18f, 15f); moveTo(15f, 12f); lineTo(15f, 14f) }, p)
            }
            Kind.PASTE -> {
                c.drawRoundRect(RectF(5f, 5f, 19f, 21f), 2f, 2f, p)
                c.drawRoundRect(RectF(9f, 3f, 15f, 7f), 1f, 1f, p)
                c.drawPath(Path().apply { moveTo(12f, 10f); lineTo(12f, 17f); moveTo(9f, 14f); lineTo(12f, 17f); lineTo(15f, 14f) }, p)
            }
            Kind.TRASH -> {
                c.drawLine(4f, 6f, 20f, 6f, p)
                c.drawPath(Path().apply { moveTo(6f, 6f); lineTo(7f, 21f); lineTo(17f, 21f); lineTo(18f, 6f) }, p)
                c.drawPath(Path().apply { moveTo(9f, 6f); lineTo(9f, 3f); lineTo(15f, 3f); lineTo(15f, 6f) }, p)
            }
            Kind.BACK -> c.drawPath(Path().apply { moveTo(20f, 12f); lineTo(4f, 12f); moveTo(10f, 6f); lineTo(4f, 12f); lineTo(10f, 18f) }, p)
        }
        c.restore()
    }
}
