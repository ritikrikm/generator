package com.td.pages.MMSRB.home;

import com.td.wrappers.BatmanWrapper;

public class MMSRBHomePage {
    private final BatmanWrapper batmanWrapper = new BatmanWrapper();

    public void loginAsUser(String group, String ssoUser) {
        batmanWrapper.selectUser(group, ssoUser);
        batmanWrapper.openApplication("MMSRB.Application.Url");
    }

    public void validateHomePageLoaded() {
        batmanWrapper.waitForVisible("MMSRB.Home.NotificationPanel.XPath");
    }

    public void validateReportWidget(String report) {
        batmanWrapper.waitForVisible(report);
    }

    public void compareNotification(String notification) {
        batmanWrapper.waitForVisible(notification);
    }

    public void compareNotificationNotPresent(String notification) {
        batmanWrapper.assertNotPresent(notification);
    }

    public void clickOnSpecificNotification(String notification) {
        batmanWrapper.click(notification);
    }

    public void validateNotificationLinking(String notification, String listView) {
        batmanWrapper.click(notification);
        batmanWrapper.validateCurrentListView(listView);
    }
}
