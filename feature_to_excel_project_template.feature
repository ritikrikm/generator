# Feature-to-Excel Project Template
#
# Purpose:
# - Use this as the standard input format for feature_to_excel.py.
# - Every row in an Examples table becomes one Excel test case.
# - Keep metadata in the Examples table when you want exact Excel output values.
#
# Required Excel-driving columns:
#   Labels, Lan, Application, UserRole, UserDisplay, Page, MainFields,
#   NotificationType, NotificationName, State
#
# Optional Excel-driving columns:
#   Description, NotificationText, NotificationCategory, Data,
#   AutoAssessment, POD, MALCODE, TestRepositoryPath
#
# Notes:
# - Use \n inside table values when you want a line break in Excel.
# - Tags above each Examples block are also used as Labels when Labels is not provided.
# - Lan can be EN or FR. Tags ending in _En or _Fr also work.

Feature: <Application> <Page> <MainFields> <NotificationType> <NotificationName>
  #Story: https://track.td.com/browse/<STORY-ID>

  Scenario Outline: <Application> <Page> notification is <State> for <Lan> <UserRole>
    Given <UserDisplay> (<Lan>) user (Retail - <UserRole>) is logged into RB
    When the user navigates to the <Page> Page
    Then the <Page>Page should load successfully
    And notification section should be displayed
    And "<NotificationText>" notification should be displayed
    And both notification should appear under "<NotificationCategory>"

    @<Application>_<Lan>
    @<Labels>
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay    | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                          | NotificationCategory                    | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | BIGBIRD-4193 | EN  | RetailRB    | PBA      | Retail Advisor | Home | GIC_RESL    | Maturity         | Notifications    | Present | # New, Uncalled GIC Maturity Leads\n# New, Uncalled RESL Maturity Opportunities | # New Marketing Leads Assigned To You | A: In Sprint Automation | Batman | HOJ     |                    |

    @<Application>_<Lan>
    @<Labels>
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay    | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                                                                         | NotificationCategory                                | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | BIGBIRD-4193 | FR  | RetailRB    | PBA      | Retail Advisor | Home | GIC_RESL    | Maturity         | Notifications    | Present | #Appels non effectués liés à de nouvelles pistes de CPG arrivant à échéance\n#Appels non effectués liés à de nouvelles opportunités CGBI arrivant à l'échéance | # Nouvelles Pistes Marketing Vous Ont été Attribuées | A: In Sprint Automation | Batman | HOJ     |                    |

    @<Application>_<Lan>
    @<Labels>
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay           | Page | MainFields | NotificationType    | NotificationName | State   | NotificationText                                                                  | NotificationCategory                       | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | BIGBIRD-4193 | EN  | RetailRB    | BM       | Retail Branch Manager | Home | GIC_RESL    | Maturity_Distribute | Notifications    | Present | # Unassigned GIC Maturity Leads to Distribute\n# Unassigned RESL Maturity Opportunities to Distribute | # Unassigned marketing leads to distribute | A: In Sprint Automation | Batman | HOJ     |                    |


# Generic functional test template for non-notification flows.
# If you do not provide Application/Page/MainFields/etc., the Excel Test Summary
# will be built from the Scenario Outline title after placeholder replacement.

  Scenario Outline: As <SSOUser> should be able to complete <BusinessAction>
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" navigates to "<Application>" from the App Launcher
    And "User" clicks on "<PrimaryButton>" button
    Then "User" validates the "<PopupName>" popup for "<FieldLabels>"
    And "User" Adds "<TargetUser>" to "<TargetContainer>"
    And "User" Remove "<TargetUser>" from "<TargetContainer>"

    @<Cycle>_<Lan>
    @<Labels>
    @<Application>_<Lan>
    @<RegressionTag>
    Examples:
      | Labels         | Lan | Application      | SSOUser                     | BusinessAction                  | PrimaryButton        | PopupName           | FieldLabels                         | TargetUser       | TargetContainer |
      | TCEPSCRMP-41138 | EN  | ColleagueConsole | RETAIL_AdminUserId          | add and remove branches for MMS Users | Add Users to Branch | Add Users to Branch | CC.AddUserstoBranch.FieldLabels     | MMSRB_FieldUserId | branch 1020     |
      | TCEPSCRMP-41139 | EN  | ColleagueConsole | ColleagueConsole_AdminUserId | add and remove branches for MMS Users | Add Users to Branch | Add Users to Branch | CC.AddUserstoBranch.FieldLabels     | MDDS_FieldName    | branch 1020     |
