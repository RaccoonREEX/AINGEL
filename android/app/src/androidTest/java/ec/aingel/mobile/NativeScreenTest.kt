package ec.aingel.mobile

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import java.util.UUID

/** Synthetic end-to-end UI smoke; does not request microphone or camera access. */
class NativeScreenTest {
    @get:Rule val ui = createAndroidComposeRule<MainActivity>()
    private fun text(id: Int) = ui.activity.getString(id)
    private fun awaitText(value: String) {
        ui.waitUntil(25000) {
            try { ui.onAllNodesWithText(value, substring = false).fetchSemanticsNodes().isNotEmpty() }
            catch (failure: IllegalStateException) {
                if (failure.message?.contains("No compose hierarchies found") == true) false else throw failure
            }
        }
    }
    private fun click(id: Int) = ui.onNodeWithText(text(id), substring = false).performScrollTo().performClick()

    @Test fun registrationProfileSettingsAndSecurityScreens() {
        // This workflow is intended for the initial signed-out test installation.
        // It never signs an existing user out to make room for test credentials.
        awaitText(text(R.string.sign_in))
        val suffix = UUID.randomUUID().toString().take(8)
        val username = "aingel.mobile.ui.$suffix"
        val password = "Synthetic-UI!" + UUID.randomUUID().toString()
        ui.onNodeWithText(text(R.string.username)).performTextInput(username)
        ui.onNodeWithText(text(R.string.password)).performTextInput(password)
        click(R.string.register)
        awaitText(text(R.string.profile))
        ui.onNodeWithText(text(R.string.name)).performTextInput("Synthetic UI profile")
        click(R.string.profile)
        awaitText(text(R.string.today))
        click(R.string.settings)
        awaitText(text(R.string.allergies))
        ui.onNodeWithText(text(R.string.allergies)).performTextInput("Synthetic allergy note")
        // Configure this synthetic profile as a caregiver would through Care web.
        runBlocking {
            val api = ApiClient(ui.activity.applicationContext)
            api.request("auth/session/")
            val profiles = api.request("profiles/") as JSONArray
            val profileId = profiles.getJSONObject(0).getString("id")
            val path = "profiles/$profileId/"
            api.request(path + "communication/", "PATCH", JSONObject().put("preferred_name", "Synthetic friendly name")
                .put("addressing", "formal").put("pace", "slow").put("interaction", "one_step")
                .put("distress", "contact_caregiver").put("sign_language", "lsec"))
            listOf("A", "B").forEachIndexed { index, suffix ->
                api.request(path + "routines/", "POST", JSONObject().put("title", "Synthetic routine $suffix").put("category", "other")
                    .put("at", if (index == 0) "08:00" else "09:00").put("weekdays", JSONArray((0..6).toList())).put("active", true))
            }
        }
        click(R.string.save)
        ui.waitUntil(25000) { ui.onAllNodesWithText(text(R.string.loading)).fetchSemanticsNodes().isEmpty() }
        ui.onNodeWithText(text(R.string.failed)).assertDoesNotExist()
        click(R.string.back)
        click(R.string.settings)
        awaitText("Synthetic allergy note")
        ui.onNodeWithText("Synthetic allergy note").assertExists()
        click(R.string.back)
        click(R.string.ask)
        ui.waitUntil(25000) { ui.onAllNodesWithText("Synthetic friendly name", substring = true).fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText(text(R.string.greeting_formal), substring = true).assertExists()
        click(R.string.need_support)
        ui.onNodeWithText(text(R.string.support_contact)).assertExists()
        ui.onNodeWithText(text(R.string.support_quiet)).assertDoesNotExist()
        click(R.string.today)
        ui.waitUntil(25000) { ui.onAllNodesWithText("Synthetic routine A", substring = true).fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Synthetic routine B", substring = true).assertDoesNotExist()
        click(R.string.next_item)
        ui.onNodeWithText("Synthetic routine B", substring = true).assertExists()
        ui.onNodeWithText(text(R.string.knowledge_search)).performScrollTo().performTextInput("diabetes")
        click(R.string.knowledge_search_action)
        awaitText(ui.activity.getString(R.string.knowledge_source, "MedlinePlus, National Library of Medicine"))
        ui.onNodeWithText(text(R.string.knowledge_open)).assertExists()
        ui.onNodeWithText(text(R.string.companion_question)).performScrollTo().performTextInput("Synthetic question only")
        ui.onNodeWithText(text(R.string.companion_submit)).performScrollTo().assertIsNotEnabled()
        click(R.string.back)
        click(R.string.hear)
        awaitText(text(R.string.sign_not_ready))
        ui.onNodeWithText(text(R.string.sign_lsec), substring = true).assertExists()
        ui.onNodeWithText(text(R.string.sign_waiting)).assertExists()
        click(R.string.back)
        awaitText(text(R.string.faces))
        click(R.string.faces)
        awaitText(text(R.string.face_intro))
        ui.onNodeWithText(text(R.string.enable)).assertIsDisplayed()
        click(R.string.back)
        click(R.string.security)
        awaitText(text(R.string.mfa_off))
        click(R.string.back)
        click(R.string.logout)
        awaitText(text(R.string.sign_in))
        ui.onNodeWithText(text(R.string.username)).assertIsDisplayed()
    }
}
