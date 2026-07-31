Feature: Feature To Excel Multiple Examples Test
  # This file is for testing the generator behavior.
  # Each Examples data row should create one Excel test case row.

  Scenario Outline: <Application> <Lan> <UserRole> <Page> <MainFields> <NotificationType> <NotificationName> <State>
    Given <UserDisplay> (<Lan>) user (Retail - <UserRole>) is logged into RB
    When the user navigates to the <Page> Page
    Then the <Page>Page should load successfully
    And notification section should be displayed
    And "<NotificationText>" notification should be displayed
    And both notification should appear under "<NotificationCategory>"

    @BIGBIRD-4193
    @RetailRB_En
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay           | Page | MainFields | NotificationType    | NotificationName | State   | NotificationText                                                                  | NotificationCategory                       | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | BIGBIRD-4193 | EN  | RetailRB    | PBA      | Retail Advisor        | Home | GIC_RESL    | Maturity            | Notifications    | Present | # New, Uncalled GIC Maturity Leads\n# New, Uncalled RESL Maturity Opportunities | # New Marketing Leads Assigned To You     | A: In Sprint Automation | Batman | HOJ     | RetailRB/home/notifications |
      | BIGBIRD-4193 | EN  | RetailRB    | BM       | Retail Branch Manager | Home | GIC_RESL    | Maturity_Distribute | Notifications    | Present | # Unassigned GIC Maturity Leads to Distribute\n# Unassigned RESL Maturity Opportunities to Distribute | # Unassigned marketing leads to distribute | A: In Sprint Automation | Batman | HOJ     | RetailRB/home/notifications |

    @BIGBIRD-4193
    @RetailRB_Fr
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay    | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                                                                                    | NotificationCategory                                  | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | BIGBIRD-4193 | FR  | RetailRB    | PBA      | Retail Advisor | Home | GIC_RESL    | Maturity         | Notifications    | Present | #Appels non effectues lies a de nouvelles pistes de CPG arrivant a echeance\n#Appels non effectues lies a de nouvelles opportunites CGBI arrivant a l'echeance | # Nouvelles Pistes Marketing Vous Ont ete Attribuees | A: In Sprint Automation | Batman | HOJ     | RetailRB/home/notifications |

  Scenario Outline: As <SSOUser> should be able to add and remove branch users
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" navigates to "Colleague Console" from the App Launcher
    And "User" clicks on "Add Users to Branch" button
    Then "User" validates the "Add Users to Branch" popup for "<FieldLabels>"
    And "User" Adds "<MMSUser>" to the branch "<Branch>"
    And "User" Remove "<MMSUser>" from the branch "<Branch>"

    @OCT25_En
    @CC_Regression
    Examples:
      | Labels          | Lan | TestSummary                                             | Description                                                   | SSOUser                      | MMSUser           | FieldLabels                     | Branch | AutoAssessment          | POD    | MALCODE | TestRepositoryPath |
      | TCEPSCRMP-41138 | EN  | CC_EN_Admin_Add_Remove_Branch_MMS_User                  | Verify that admin user can add and remove MMS user from branch. | RETAIL_AdminUserId           | MMSRB_FieldUserId | CC.AddUserstoBranch.FieldLabels | 1020   | A: In Sprint Automation | Batman | HOJ     | RetailRB/colleagueConsole/people |
      | TCEPSCRMP-41139 | EN  | CC_EN_Console_Admin_Add_Remove_Branch_MMS_User          | Verify that console admin can add and remove MMS user from branch. | ColleagueConsole_AdminUserId | MDDS_FieldName    | CC.AddUserstoBranch.FieldLabels | 1020   | A: In Sprint Automation | Batman | HOJ     | RetailRB/colleagueConsole/people |
