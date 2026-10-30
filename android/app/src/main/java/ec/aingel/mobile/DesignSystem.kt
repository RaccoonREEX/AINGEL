package ec.aingel.mobile

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Tokens from AINGEL UI tokens.json v1.1.1 (1 px = 1 dp, text px = sp). */
object Ui {
    val Navy = Color(0xFF092E66); val Blue = Color(0xFF0756B1); val Gold = Color(0xFFEBA934)
    val Text = Color(0xFF1A2740); val Placeholder = Color(0xFF7A869C); val Disabled = Color(0xFF9AA6BA)
    val Subtle = Color(0xFFF6F8FB); val Selected = Color(0xFFEAF0F8); val RingPending = Color(0xFFC9D2E0)
    // High contrast (ESPECIFICACION 6): muted text -> #1A2740, borders -> #5A6780.
    var Muted by mutableStateOf(Color(0xFF5A6780)); private set
    var Border by mutableStateOf(Color(0xFFE4E8EF)); private set
    var Divider by mutableStateOf(Color(0xFFEDF0F5)); private set
    var Control by mutableStateOf(Color(0xFFD9E0EA)); private set
    fun highContrast(on: Boolean) {
        Muted = if (on) Color(0xFF1A2740) else Color(0xFF5A6780)
        Border = if (on) Color(0xFF5A6780) else Color(0xFFE4E8EF)
        Divider = if (on) Color(0xFF5A6780) else Color(0xFFEDF0F5)
        Control = if (on) Color(0xFF5A6780) else Color(0xFFD9E0EA)
    }
    val Font = FontFamily(Font(R.font.montserrat_regular, FontWeight.Normal), Font(R.font.montserrat_medium, FontWeight.Medium),
        Font(R.font.montserrat_semibold, FontWeight.SemiBold), Font(R.font.montserrat_bold, FontWeight.Bold))
}

/** Text in Montserrat; sizes follow the mock-up and scale with the profile's large-text preference. */
val LocalTextScale = compositionLocalOf { 1f }
@Composable fun T(text: String, size: Int, weight: FontWeight = FontWeight.Normal, color: Color = Ui.Text, modifier: Modifier = Modifier,
                  align: TextAlign? = null, lineHeight: Float = 1.4f, letterSpacing: TextUnit = TextUnit.Unspecified, maxLines: Int = Int.MAX_VALUE) {
    val scale = LocalTextScale.current
    Text(text, modifier, color = color, fontSize = (size * scale).sp, fontWeight = weight, fontFamily = Ui.Font, textAlign = align,
        lineHeight = (size * scale * lineHeight).sp, letterSpacing = letterSpacing, maxLines = maxLines,
        overflow = if (maxLines == Int.MAX_VALUE) androidx.compose.ui.text.style.TextOverflow.Clip else androidx.compose.ui.text.style.TextOverflow.Ellipsis)
}
@Composable fun Overline(text: String, color: Color = Ui.Muted) = T(text.uppercase(), 11, FontWeight.SemiBold, color, letterSpacing = 1.5.sp)

@Composable fun PrimaryButton(label: String, modifier: Modifier = Modifier, height: Dp = 54.dp, enabled: Boolean = true, shadow: Boolean = false, fill: Boolean = true, onClick: () -> Unit) {
    Button(onClick, modifier.then(if (fill) Modifier.fillMaxWidth() else Modifier).heightIn(min = height).then(if (shadow) Modifier.shadow(10.dp, RoundedCornerShape(16.dp), ambientColor = Ui.Navy, spotColor = Ui.Navy) else Modifier),
        enabled = enabled, shape = RoundedCornerShape(16.dp), colors = ButtonDefaults.buttonColors(Ui.Navy, Color.White, Ui.Navy.copy(alpha = 0.45f), Color.White),
        contentPadding = PaddingValues(horizontal = if (fill) 16.dp else 22.dp)) {
        T(label, if (fill) 16 else 14, FontWeight.SemiBold, Color.White, align = TextAlign.Center, maxLines = if (fill) Int.MAX_VALUE else 1)
    }
}
@Composable fun OutlineButton(label: String, modifier: Modifier = Modifier, height: Dp = 54.dp, enabled: Boolean = true, navyBorder: Boolean = false, size: Int = 16, onClick: () -> Unit) {
    OutlinedButton(onClick, modifier.fillMaxWidth().heightIn(min = height), enabled = enabled, shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.5.dp, if (navyBorder) Ui.Navy else Ui.Control), colors = ButtonDefaults.outlinedButtonColors(Color.White, Ui.Navy)) {
        T(label, size, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center)
    }
}
@Composable fun LinkButton(label: String, modifier: Modifier = Modifier, size: Int = 13, color: Color = Ui.Blue, onClick: () -> Unit) {
    Box(modifier.heightIn(min = 44.dp).clip(RoundedCornerShape(8.dp)).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 4.dp), contentAlignment = Alignment.Center) {
        T(label, size, FontWeight.SemiBold, color)
    }
}

/** Labelled input: 13/600 navy label, 54 dp field, radius 14, border 1.5 (blue with halo when focused). */
@Composable fun FieldInput(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, secret: Boolean = false,
                           height: Dp = 54.dp, fontSize: Int = 16, placeholder: String = "", keyboard: KeyboardType = KeyboardType.Text, enabled: Boolean = true) {
    var focused by remember { mutableStateOf(false) }
    var shown by remember { mutableStateOf(false) }
    val scale = LocalTextScale.current
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        T(label, 13, FontWeight.SemiBold, Ui.Navy)
        BasicTextField(value, onChange, enabled = enabled, singleLine = true,
            textStyle = TextStyle(fontFamily = Ui.Font, fontSize = (fontSize * scale).sp, color = Ui.Text),
            visualTransformation = if (secret && !shown) PasswordVisualTransformation() else VisualTransformation.None,
            keyboardOptions = KeyboardOptions(keyboardType = if (secret) KeyboardType.Password else keyboard), cursorBrush = SolidColor(Ui.Blue),
            modifier = Modifier.fillMaxWidth().semantics { contentDescription = label }.onFocusChangedCompat { focused = it }) { inner ->
            Row(Modifier.fillMaxWidth().heightIn(min = height)
                .then(if (focused) Modifier.border(3.dp, Ui.Blue.copy(alpha = 0.12f), RoundedCornerShape(16.dp)).padding(1.5.dp) else Modifier)
                .border(1.5.dp, if (focused) Ui.Blue else Ui.Control, RoundedCornerShape(14.dp)).background(Color.White, RoundedCornerShape(14.dp))
                .padding(start = 16.dp, end = if (secret) 4.dp else 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f)) { if (value.isEmpty() && placeholder.isNotEmpty()) T(placeholder, fontSize, color = Ui.Placeholder); inner() }
                if (secret) LinkButton(if (shown) stringRes(R.string.ui_hide) else stringRes(R.string.ui_show)) { shown = !shown }
            }
        }
    }
}

@Composable fun stringRes(id: Int): String = androidx.compose.ui.res.stringResource(id)

/** Segmented / choice button: navy fill when selected. */
@Composable fun Choice(label: String, selected: Boolean, modifier: Modifier = Modifier, height: Dp = 46.dp, size: Int = 14, start: Boolean = false, onClick: () -> Unit) {
    Box(modifier.heightIn(min = height).clip(RoundedCornerShape(12.dp)).background(if (selected) Ui.Navy else Color.White)
        .border(1.5.dp, if (selected) Ui.Navy else Ui.Control, RoundedCornerShape(12.dp))
        .selectable(selected, role = Role.RadioButton, onClick = onClick).padding(horizontal = if (start) 16.dp else 2.dp),
        contentAlignment = if (start) Alignment.CenterStart else Alignment.Center) {
        // Short labels stay on one line (no mid-word breaks with a raised system font size).
        Text(label, color = if (selected) Color.White else Ui.Navy, fontSize = (size * LocalTextScale.current).sp, fontFamily = Ui.Font,
            fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center, maxLines = if (start) Int.MAX_VALUE else 1, softWrap = start)
    }
}

/** Radio row (2e): 20 dp circle with navy fill and white inner ring. */
@Composable fun RadioCard(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).border(1.5.dp, if (selected) Ui.Navy else Ui.Border, RoundedCornerShape(14.dp))
        .selectable(selected, role = Role.RadioButton, onClick = onClick).padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(20.dp).border(2.dp, if (selected) Ui.Navy else Ui.RingPending, CircleShape).padding(3.dp).background(if (selected) Ui.Navy else Color.White, CircleShape))
        T(label, 14, FontWeight.SemiBold, Ui.Navy)
    }
}

/** Routine ring: navy with check (done), gold (next), grey (pending). */
@Composable fun Ring(done: Boolean, next: Boolean, size: Dp = 28.dp, modifier: Modifier = Modifier) {
    Box(modifier.size(size).border(2.dp, when { done -> Ui.Navy; next -> Ui.Gold; else -> Ui.RingPending }, CircleShape)
        .background(if (done) Ui.Navy else Color.Transparent, CircleShape), contentAlignment = Alignment.Center) {
        if (done) T("✓", 13, FontWeight.Bold, Color.White)
    }
}

@Composable fun ProgressLine(fraction: Float, gold: Boolean = false, height: Dp = 4.dp) {
    Box(Modifier.fillMaxWidth().height(height).clip(RoundedCornerShape(50)).background(Ui.Divider)) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).fillMaxHeight().clip(RoundedCornerShape(50)).background(if (gold) Ui.Gold else Ui.Navy))
    }
}

@Composable fun Dot(color: Color, size: Dp = 8.dp) = Box(Modifier.size(size).background(color, CircleShape))

@Composable fun Avatar(initials: String, size: Dp = 44.dp) {
    Box(Modifier.size(size).background(Ui.Navy, CircleShape), contentAlignment = Alignment.Center) { T(initials, 14, FontWeight.SemiBold, Color.White) }
}

/** 1f bottom bar: five text-only tabs; the active one sits on a #EAF0F8 pill. */
@Composable fun TabBar(tabs: List<Pair<String, String>>, active: String, onSelect: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().background(Color.White).navigationBarsPadding()) {
        HorizontalDivider(color = Ui.Divider)
        Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp, top = 8.dp, bottom = 2.dp)) {
            tabs.forEach { (route, label) ->
                val on = route == active
                // Labels never truncate: only the active pill has padding and it may extend past its cell,
                // which keeps the five tabs readable with the system font size raised.
                Box(Modifier.weight(1f).height(48.dp).selectable(on, role = Role.Tab) { onSelect(route) }, contentAlignment = Alignment.Center) {
                    Box(Modifier.wrapContentWidth(unbounded = true).clip(RoundedCornerShape(50)).background(if (on) Ui.Selected else Color.Transparent)
                        .padding(horizontal = if (on) 10.dp else 0.dp, vertical = 7.dp)) {
                        Text(label, color = if (on) Ui.Navy else Ui.Muted, fontSize = (12 * LocalTextScale.current).sp, fontFamily = Ui.Font,
                            fontWeight = if (on) FontWeight.Bold else FontWeight.SemiBold, maxLines = 1, softWrap = false)
                    }
                }
            }
        }
    }
}

/** 76 dp navy microphone / stop button with the primary shadow. */
@Composable fun MicButton(busy: Boolean, label: String, size: Dp = 76.dp, onClick: () -> Unit) {
    Box(Modifier.size(size).shadow(12.dp, CircleShape, ambientColor = Ui.Navy, spotColor = Ui.Navy).clip(CircleShape).background(Ui.Navy)
        .clickable(role = Role.Button, onClickLabel = label, onClick = onClick).semantics { contentDescription = label }, contentAlignment = Alignment.Center) {
        if (busy) Box(Modifier.size(size * 0.26f).background(Color.White, RoundedCornerShape(5.dp)))
        else androidx.compose.foundation.Canvas(Modifier.size(size * 0.37f)) {
            val w = this.size.width; val stroke = androidx.compose.ui.graphics.drawscope.Stroke(w * 0.075f, cap = androidx.compose.ui.graphics.StrokeCap.Round)
            drawRoundRect(Color.White, androidx.compose.ui.geometry.Offset(w * 0.375f, w * 0.125f), androidx.compose.ui.geometry.Size(w * 0.25f, w * 0.458f),
                androidx.compose.ui.geometry.CornerRadius(w * 0.125f), style = stroke)
            drawArc(Color.White, 0f, 180f, false, androidx.compose.ui.geometry.Offset(w * 0.229f, w * 0.188f), androidx.compose.ui.geometry.Size(w * 0.542f, w * 0.542f), style = stroke)
            drawLine(Color.White, androidx.compose.ui.geometry.Offset(w / 2, w * 0.73f), androidx.compose.ui.geometry.Offset(w / 2, w * 0.875f), w * 0.075f, androidx.compose.ui.graphics.StrokeCap.Round)
        }
    }
}

/** Small focus helper kept local so the field can draw its own focus ring. */
fun Modifier.onFocusChangedCompat(onChange: (Boolean) -> Unit) = this.onFocusChanged { onChange(it.isFocused) }
