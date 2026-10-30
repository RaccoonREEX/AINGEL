package ec.aingel.mobile

import org.junit.Assert.assertEquals
import org.junit.Test

class FoldablesTest {
    @Test fun outerScreensShowOnlyTheOrb() {
        assertEquals(WindowShape.COVER, windowShape(173, 341, secondaryDisplay = true))   // Flip 3/4 · 1,9″ (260×512 px)
        assertEquals(WindowShape.COVER, windowShape(360, 374, secondaryDisplay = true))   // Flip 5/6 · 3,4″ Flex Window
        assertEquals(WindowShape.COVER, windowShape(410, 406, secondaryDisplay = true))   // razr+ · 3,6″
        assertEquals(WindowShape.COVER, windowShape(360, 374, secondaryDisplay = false))  // any small window (< 400 dp)
    }

    @Test fun phoneAndWideScreensKeepTheirLayouts() {
        assertEquals(WindowShape.PHONE, windowShape(411, 914, secondaryDisplay = false))      // Flip 4 open
        assertEquals(WindowShape.PHONE, windowShape(384, 853, secondaryDisplay = false))      // larger display zoom
        assertEquals(WindowShape.TWO_PANE, windowShape(673, 841, secondaryDisplay = false))   // Fold · 7,6″ inner
        assertEquals(WindowShape.TWO_PANE, windowShape(914, 411, secondaryDisplay = false))   // phone in landscape
    }
}
