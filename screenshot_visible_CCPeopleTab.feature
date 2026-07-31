Feature: Colleague Console People Tab
  #Story: https://track.td.com/browse/CEPSCRMP-20209

  Scenario Outline: As <SSOUser> should be able to add and remove branches for MMS Users
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" navigates to "Colleague Console" from the App Launcher
    And "User" clicks on "Show Navigation Menu" button
    And "User" select "People" from dropdown

    @TCEPSCRMP-16160
    @CC_Regression
    Examples:
      | SSOUser                      |
      | ColleagueConsole_AdminUserId |

  Scenario Outline: As <SSOUser> should be able to add and remove branches for MMS Users
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" navigates to "Colleague Console" from the App Launcher
    And "User" clicks on "Add Users to Branch" button
    Then "User" validates the "Add Users to Branch" popup for "CC.AddUserstoBranch.FieldLabels"
    And "User" Adds "<MMSUser>" to the branch "1020"
    And "User" Remove "<MMSUser>" from the branch "1020"

    @OCT25_En
    @TCEPSCRMP-41138
    @CC_En
    @CC_Regression
    Examples:
      | SSOUser            | MMSUser            |
      | RETAIL_AdminUserId | MMSRB_FieldUserId  |

    @OCT25_En
    @TCEPSCRMP-41139
    @CC_En
    @CC_Regression
    Examples:
      | SSOUser                      | MMSUser        |
      | ColleagueConsole_AdminUserId | MDDS_FieldName |

  Scenario Outline: As <SSOUser> should be able to add and remove Campaign for MMS Users
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" navigates to "Colleague Console" from the App Launcher
    And "User" clicks on "Add Users to Campaign" button
    Then "User" validates the "Add Users to Campaign" popup for "CC.AddUserstoCampaign.FieldLabels"
    And "User" Adds "<MMSUser>" to the campaign "Mobile Mortgage Specialist - Mortgages"
    And "User" Remove "<MMSUser>" from the campaign "Mobile Mortgage Specialist - Mortgages"

    @OCT25_En
    @TCEPSCRMP-41140
    @CC_En
    @CC_Regression
    Examples:
      | SSOUser            | MMSUser           |
      | RETAIL_AdminUserId | MMSRB_FieldUserId |

    @OCT25_En
    @TCEPSCRMP-41141
    @CC_En
    @CC_Regression
    Examples:
      | SSOUser                      | MMSUser        |
      | ColleagueConsole_AdminUserId | MDDS_FieldName |
