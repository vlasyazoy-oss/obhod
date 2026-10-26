package org.obhod.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View
import kotlin.math.sin

/**
 * Эмблема «Обхода» и кнопка подключения. Геометрия как в core/emblem.py (координаты рисунка 1280×845).
 * Глаза закрыты — отключено, открыты — подключено, бегают — идёт подключение.
 */
class EmblemView(context: Context) : View(context) {
    var eyesOpen = false
        set(v) { field = v; invalidate() }
    var busy = false
        set(v) { field = v; startTime = System.currentTimeMillis(); invalidate() }

    private var startTime = 0L
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        setMeasuredDimension(w, w * H / W)
    }

    override fun onDraw(canvas: Canvas) {
        val s = width.toFloat() / W
        fun path(pts: List<Pair<Int, Int>>) = Path().apply {
            pts.forEachIndexed { i, (x, y) -> if (i == 0) moveTo(x * s, y * s) else lineTo(x * s, y * s) }
            close()
        }
        paint.style = Paint.Style.FILL
        paint.color = WHITE
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
        paint.color = BLUE
        canvas.drawPath(path(LEFT), paint)
        paint.color = PLUM
        canvas.drawPath(path(RIGHT), paint)
        paint.color = Color.BLACK
        canvas.drawRect(497 * s, 349 * s, 772 * s, 497 * s, paint)

        val look = if (busy) sin((System.currentTimeMillis() - startTime) / 180.0).toFloat() else 0f
        for ((cx, cy) in listOf(530 to 423, 739 to 423)) {
            if (eyesOpen || busy) {
                paint.color = WHITE
                canvas.drawOval(RectF((cx - 58) * s, (cy - 72) * s, (cx + 58) * s, (cy + 72) * s), paint)
                paint.color = Color.BLACK
                val px = cx + look * 18 + if (cx < W / 2) 6 else -6
                canvas.drawCircle(px * s, cy * s, 34 * s, paint)
            } else {
                paint.color = WHITE
                paint.style = Paint.Style.STROKE
                paint.strokeWidth = 9 * s
                paint.strokeCap = Paint.Cap.ROUND
                canvas.drawArc(RectF((cx - 52) * s, (cy - 30) * s, (cx + 52) * s, (cy + 22) * s), 20f, 140f, false, paint)
                paint.style = Paint.Style.FILL
            }
        }
        if (busy) postInvalidateOnAnimation()
    }

    companion object {
        const val W = 1280
        const val H = 845
        val BLUE = Color.parseColor("#22408a")
        val PLUM = Color.parseColor("#554452")
        const val WHITE = Color.WHITE
        private val LEFT = listOf(0 to 0, 539 to 0, 539 to 182, 346 to 278, 346 to 567, 539 to 663, 539 to H, 0 to H)
        private val RIGHT = listOf(725 to 0, W to 0, W to H, 725 to H, 725 to 665, 922 to 567, 922 to 278, 725 to 180)
    }
}
