package ec.aingel.mobile

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/**
 * «Autorizaciones»: the person's own decisions, one purpose at a time (backend care.consent). Each purpose can be read
 * aloud with the phone's own voice. Whoever set the profile up for another adult sees the state and can create the
 * one-time code; they never decide for the person. Helping someone operate the screen is not deciding for them.
 */
@Composable fun ConsentScreen(model: AingelViewModel, s: MobileState, onBack: () -> Unit) {
    val profileId = s.profile?.optString("id").orEmpty()
    LaunchedEffect(profileId) { if (profileId.isNotBlank()) model.loadConsent() }
    val state = s.consent
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 12.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BackChevron(onBack)
        T(stringResource(R.string.consent_title), 24, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.semantics { heading() })
        ErrorText(s)
        if (state == null) { T(stringResource(R.string.loading), 14, color = Ui.Muted); return@Column }
        val status = state.optString("subject_status")
        T(stringResource(when (status) {
            "self", "subject_linked" -> if (state.optBoolean("is_subject")) R.string.consent_yours else R.string.consent_theirs
            "requires_legal_review" -> R.string.consent_legal_review_state
            else -> R.string.consent_pending_state
        }), 14, color = Ui.Text, lineHeight = 1.45f, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        when {
            state.optBoolean("is_subject") -> Purposes(state, decide = true, model = model, busy = s.busy)
            status == "pending_consent" -> PendingSubject(model, s)
            status == "requires_legal_review" -> {}
            else -> Purposes(state, decide = false, model = model, busy = s.busy)
        }
        T(state.optString("credits_notice"), 12, color = Ui.Muted, lineHeight = 1.45f)
        // Someone may also have set up a profile for this account's holder.
        androidx.compose.foundation.layout.Spacer(Modifier.padding(top = 8.dp))
        RedeemCode(model, s)
    }
}

@Composable private fun Purposes(state: JSONObject, decide: Boolean, model: AingelViewModel, busy: Boolean) {
    val purposes = state.optJSONArray("purposes")?.rows().orEmpty()
    listOf("local" to R.string.consent_group_local, "aingel" to R.string.consent_group_aingel, "meta" to R.string.consent_group_meta).forEach { (to, label) ->
        val group = purposes.filter { it.optString("to") == to }
        if (group.isEmpty()) return@forEach
        T(stringResource(label), 13, FontWeight.SemiBold, Ui.Muted, modifier = Modifier.padding(top = 6.dp))
        group.forEach { purpose -> PurposeCard(purpose, decide, model, busy) }
    }
}

@Composable private fun PurposeCard(purpose: JSONObject, decide: Boolean, model: AingelViewModel, busy: Boolean) {
    val status = purpose.optString("status")
    val title = purpose.optString("title"); val detail = purpose.optString("detail")
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(if (status == "granted") Ui.Selected else androidx.compose.ui.graphics.Color.White)
        .border(1.5.dp, if (status == "granted") Ui.Navy else Ui.Control, RoundedCornerShape(16.dp)).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        T(title, 16, FontWeight.SemiBold, Ui.Navy)
        T(detail, 13, color = Ui.Text, lineHeight = 1.45f)
        // The state in words, not only colour.
        T(stringResource(when (status) { "granted" -> R.string.consent_granted; "declined" -> R.string.consent_declined; "revoked" -> R.string.consent_revoked; else -> R.string.consent_undecided }),
            13, FontWeight.SemiBold, if (status == "granted") Ui.Navy else Ui.Muted)
        LinkButton(stringResource(R.string.consent_listen), size = 14) { model.speak("$title. $detail") }
        // Decisions on their own row: wide enough for large text and a narrow (Flip) screen.
        if (decide) Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            when (status) {
                "granted" -> OutlineButton(stringResource(R.string.consent_revoke), Modifier.weight(1f), 44.dp, enabled = !busy, size = 13) { model.decideConsent(purpose.optString("id"), "revoke") }
                "pending" -> {
                    OutlineButton(stringResource(R.string.consent_decline), Modifier.weight(1f), 44.dp, enabled = !busy, size = 13) { model.decideConsent(purpose.optString("id"), "decline") }
                    PrimaryButton(stringResource(R.string.consent_allow), Modifier.weight(1f), 44.dp, enabled = !busy) { model.decideConsent(purpose.optString("id"), "grant") }
                }
                else -> PrimaryButton(stringResource(R.string.consent_allow), Modifier.weight(1f), 44.dp, enabled = !busy) { model.decideConsent(purpose.optString("id"), "grant") }
            }
        }
    }
}

/** Set up for another adult: the one-time code for them, or recording that they cannot consent (nothing enabled). */
@Composable private fun PendingSubject(model: AingelViewModel, s: MobileState) {
    var confirmLegal by remember { mutableStateOf(false) }
    T(stringResource(R.string.consent_code_intro), 14, color = Ui.Text, lineHeight = 1.45f)
    s.consentCode?.let { code ->
        T(code.optString("code").chunked(4).joinToString(" "), 34, FontWeight.Bold, Ui.Navy, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        T(stringResource(R.string.consent_code_expiry), 12, color = Ui.Muted, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        OutlineButton(stringResource(R.string.consent_code_read), height = 46.dp) { model.speak(code.optString("code").toList().joinToString(", ")) }
    }
    PrimaryButton(stringResource(if (s.consentCode == null) R.string.consent_code_create else R.string.consent_code_again), height = 50.dp, enabled = !s.busy) { model.createConsentCode() }
    if (!confirmLegal) LinkButton(stringResource(R.string.consent_legal_review), size = 13, color = Ui.Muted) { confirmLegal = true }
    else Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        T(stringResource(R.string.consent_legal_review_explain), 13, color = Ui.Text, lineHeight = 1.45f)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlineButton(stringResource(R.string.cancel), Modifier.weight(1f), 44.dp, size = 13) { confirmLegal = false }
            PrimaryButton(stringResource(R.string.consent_legal_review_confirm), Modifier.weight(1f), 44.dp, enabled = !s.busy) { model.requestLegalReview(); confirmLegal = false }
        }
    }
}

/** «Tengo un código de AINGEL»: the person links their own adult account to the profile set up for them. */
@Composable fun RedeemCode(model: AingelViewModel, s: MobileState) {
    var code by remember { mutableStateOf("") }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        T(stringResource(R.string.consent_redeem_title), 15, FontWeight.SemiBold, Ui.Navy)
        T(stringResource(R.string.consent_redeem_intro), 12, color = Ui.Muted, lineHeight = 1.45f)
        FieldInput(stringResource(R.string.consent_redeem_label), code, { value -> code = value.filter { it.isDigit() }.take(8) }, height = 50.dp, fontSize = 18)
        PrimaryButton(stringResource(R.string.consent_redeem_go), height = 48.dp, enabled = !s.busy && code.length == 8) { model.redeemConsentCode(code); code = "" }
    }
}

/** Accounts created before the age policy: the explicit 18+ declaration, before anything else. */
@Composable fun AdultDeclaration(model: AingelViewModel, s: MobileState) {
    var adult by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(start = 24.dp, end = 24.dp, top = 30.dp, bottom = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        T(stringResource(R.string.adult_title), 24, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.semantics { heading() })
        T(stringResource(R.string.adult_explain), 14, color = Ui.Text, lineHeight = 1.5f)
        Choice((if (adult) "✓  " else "") + stringResource(R.string.adult_statement), adult, Modifier.fillMaxWidth(), start = true) { adult = !adult }
        ErrorText(s)
        PrimaryButton(stringResource(R.string.setup_continue), height = 52.dp, enabled = adult && !s.busy) { model.declareAdult() }
        LinkButton(stringResource(R.string.logout), Modifier.align(Alignment.CenterHorizontally), size = 13, color = Ui.Muted) { model.logout() }
    }
}
