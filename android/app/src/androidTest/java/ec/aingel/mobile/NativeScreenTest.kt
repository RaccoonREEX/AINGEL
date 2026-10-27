package ec.aingel.mobile

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Rule
import org.junit.Test
import java.util.UUID

/** Synthetic end-to-end UI smoke; does not request microphone or camera access. */
class NativeScreenTest {
    @get:Rule val ui = createAndroidComposeRule<MainActivity>()
    private fun text(id: Int) = ui.activity.getString(id)
    private fun awaitText(value: String) {
        ui.waitUntil(25000) { ui.onAllNodesWithText(value, substring = false).fetchSemanticsNodes().isNotEmpty() }
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
        click(R.string.save)
        ui.waitUntil(25000) { ui.onAllNodesWithText(text(R.string.loading)).fetchSemanticsNodes().isEmpty() }
        ui.onNodeWithText(text(R.string.failed)).assertDoesNotExist()
        click(R.string.back)
        click(R.string.settings)
        awaitText("Synthetic allergy note")
        ui.onNodeWithText("Synthetic allergy note").assertExists()
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
