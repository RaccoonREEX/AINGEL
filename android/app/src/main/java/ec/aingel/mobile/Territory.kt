package ec.aingel.mobile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/*
 * Meta's Restricted Territories (backend care.territory): Meta does not allow its AI to be offered to people located
 * in some territories. The person answers; the server keeps only the answer, never the country or a location.
 */
internal const val TERRITORY_OUTSIDE = "outside_restricted"
internal const val TERRITORY_INSIDE = "inside_restricted"

/** The account's answer from a session payload: "" when it has not answered for the current policy version. Signed
 * out (no user) counts as outside, so nothing is gated before a session exists. */
internal fun territoryOf(session: JSONObject): String {
    val user = session.optJSONObject("user") ?: return TERRITORY_OUTSIDE
    return if (user.isNull("territory")) "" else user.optString("territory")
}

/** The fields the server expects with the account's answer and the policy version it sent. */
internal fun territoryFields(body: JSONObject, answer: String, version: String): JSONObject =
    body.put("territory", answer).put("territory_version", version)

/** Meta's list in the app language, as the server sent it. */
internal fun restrictedList(session: JSONObject?, spanish: Boolean): String =
    session?.optJSONObject("restricted_territories")?.optString(if (spanish) "es-EC" else "en-US").orEmpty()

private fun spanish() = java.util.Locale.getDefault().language == "es"

/** Two radio choices, neither chosen by default, with Meta's list and what is kept read with them. */
@Composable internal fun TerritoryChoice(answer: String?, onAnswer: (String) -> Unit, list: String, account: Boolean) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        T(stringResource(R.string.territory_question), 14, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.semantics { heading() })
        RadioCard(stringResource(R.string.territory_outside), answer == TERRITORY_OUTSIDE) { onAnswer(TERRITORY_OUTSIDE) }
        RadioCard(stringResource(R.string.territory_inside), answer == TERRITORY_INSIDE) { onAnswer(TERRITORY_INSIDE) }
        T(stringResource(R.string.territory_explain, list), 11, color = Ui.Muted, lineHeight = 1.45f)
        if (answer == TERRITORY_INSIDE) {
            T(stringResource(if (account) R.string.territory_inside_account else R.string.territory_inside_signup), 13,
                color = Color(0xFF8B2630), modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite })
        }
    }
}

/** Accounts from before the territory policy answer once; an account declared inside sees why AINGEL is closed and
 * can update the answer when it is no longer there. */
@Composable fun TerritoryDeclaration(model: AingelViewModel, s: MobileState) {
    var answer by remember { mutableStateOf<String?>(null) }
    val inside = s.territory == TERRITORY_INSIDE
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 24.dp, end = 24.dp, top = 30.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)) {
        T(stringResource(if (inside) R.string.territory_closed_title else R.string.adult_title_before), 24, FontWeight.SemiBold, Ui.Navy,
            modifier = Modifier.semantics { heading() })
        T(stringResource(if (inside) R.string.territory_closed_explain else R.string.territory_intro), 14, color = Ui.Text, lineHeight = 1.5f)
        TerritoryChoice(answer, { answer = it }, restrictedList(s.restrictedTerritories, spanish()), account = true)
        ErrorText(s)
        PrimaryButton(stringResource(R.string.setup_continue), height = 52.dp, enabled = answer != null && !s.busy) { answer?.let { model.declareTerritory(it) } }
        LinkButton(stringResource(R.string.logout), Modifier.align(Alignment.CenterHorizontally), size = 13, color = Ui.Muted) { model.logout() }
    }
}
