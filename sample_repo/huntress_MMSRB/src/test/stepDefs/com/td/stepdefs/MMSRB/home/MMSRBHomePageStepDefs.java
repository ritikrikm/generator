package com.td.stepdefs.MMSRB.home;

import com.td.pages.MMSRB.home.MMSRBHomePage;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

public class MMSRBHomePageStepDefs {
    private final MMSRBHomePage mmsrbHomePage = new MMSRBHomePage();

    @Given("{string} successfully logs in to RB with {string}")
    public void userSuccessfullyLogsInToRBWith(String group, String ssoUser) {
        mmsrbHomePage.loginAsUser(group, ssoUser);
    }

    @When("{string} should be redirected to salesforce RB home page")
    public void userShouldBeRedirectedToSalesforceRBHomePage(String group) {
        mmsrbHomePage.validateHomePageLoaded();
    }

    @Then("{string} should able to see the {string} notifications")
    public void userShouldAbleToSeeTheNotifications(String group, String report) {
        mmsrbHomePage.validateReportWidget(report);
    }

    @And("{string} should be able to see {string} notification")
    public void shouldBeAbleToSeeNotification(String group, String notification) {
        mmsrbHomePage.compareNotification(notification);
    }

    @And("{string} should NOT be able to see {string} notification")
    public void shouldNOTBeAbleToSeeNotification(String group, String notification) {
        mmsrbHomePage.compareNotificationNotPresent(notification);
    }

    @Then("{string} clicks on {string} notification")
    public void clicksOnNotification(String group, String notification) {
        mmsrbHomePage.clickOnSpecificNotification(notification);
    }

    @And("{string} see {string} correctly linked to {string} listview")
    public void seeCorrectlyLinkedToListview(String group, String notification, String listView) {
        mmsrbHomePage.validateNotificationLinking(notification, listView);
    }
}
