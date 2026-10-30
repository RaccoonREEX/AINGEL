package ec.aingel.mobile

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.BeforeClass
import org.junit.Rule
import org.junit.Test
import java.util.UUID

/** Synthetic end-to-end UI smoke; does not request microphone or camera access. */
class NativeScreenTest {
    companion object {
        @JvmStatic @BeforeClass fun freezeOrb() { OrbAnimation.enabled = false }
    }
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
    /** For buttons pinned outside a scrolling area (redesigned access, setup and tab bar). */
    private fun tap(id: Int) {
        val node = ui.onAllNodesWithText(text(id), substring = false).onFirst()
        // Forms scroll (the keyboard can push the button out of view); pinned buttons have no scroll parent.
        try { node.performScrollTo() } catch (_: AssertionError) {} catch (_: IllegalStateException) {}
        node.performClick()
    }
    private fun type(label: Int, value: String) = ui.onNodeWithContentDescription(text(label)).performTextInput(value)
    private fun more() = tap(R.string.nav_more)

    @Test fun registrationProfileSettingsAndSecurityScreens() {
        // This workflow is intended for the initial signed-out test installation.
        // It never signs an existing user out to make room for test credentials.
        awaitText(text(R.string.sign_in))
        val suffix = UUID.randomUUID().toString().take(8)
        val username = "aingel.mobile.ui.$suffix"
        val password = "Synthetic-UI!" + UUID.randomUUID().toString()
        tap(R.string.register)
        awaitText(text(R.string.ui_your_name))
        type(R.string.ui_your_name, "Synthetic UI person")
        type(R.string.ui_username, username)
        type(R.string.password, password)
        ui.onNodeWithContentDescription(text(R.string.ui_username)).assertTextContains(username)
        ui.onAllNodesWithText(text(R.string.setup_continue)).onFirst().assertIsEnabled()
        tap(R.string.setup_continue)
        awaitText(text(R.string.ui_person_name))
        type(R.string.ui_person_name, "Synthetic UI profile")
        tap(R.string.setup_continue)
        tap(R.string.setup_continue)
        tap(R.string.ui_review_activate)
        tap(R.string.ui_activate)
        awaitText(text(R.string.ui_ready_title))
        tap(R.string.ui_home)
        awaitText(text(R.string.ui_hint_talk))
        more()
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
        more()
        click(R.string.settings)
        awaitText("Synthetic allergy note")
        ui.onNodeWithText("Synthetic allergy note").assertExists()
        more()
        click(R.string.ui_more_tools)
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
        more()
        click(R.string.hear)
        awaitText(text(R.string.sign_not_ready))
        ui.onNodeWithText(text(R.string.sign_lsec), substring = true).assertExists()
        ui.onNodeWithText(text(R.string.sign_waiting)).assertExists()
        more()
        awaitText(text(R.string.faces))
        click(R.string.faces)
        awaitText(text(R.string.face_intro))
        ui.onNodeWithText(text(R.string.enable)).assertIsDisplayed()
        more()
        click(R.string.security)
        awaitText(text(R.string.mfa_off))
        more()
        click(R.string.logout)
        awaitText(text(R.string.sign_in))
        ui.onNodeWithText(text(R.string.register)).assertIsDisplayed()
    }
}
