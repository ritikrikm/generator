Feature: RetailRB Home Maturity Notifications

  Scenario Outline: RetailRB home maturity notifications are present for <Lan> <UserRole>
    Given <UserDisplay> (<Lan>) user (Retail - <UserRole>) is logged into RB
    When the user navigates to the Home Page
    Then the HomePage should load successfully
    And notification section should be displayed
    And "<NotificationText>" notification should be displayed
    And both notification should appear under "<NotificationCategory>"

    @RetailRB_En
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay    | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                          | NotificationCategory                    | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | EN  | RetailRB    | PBA      | Retail Advisor | Home | GIC_RESL    | Maturity         | Notifications    | Present | # New, Uncalled GIC Maturity Leads\n# New, Uncalled RESL Maturity Opportunities | # New Marketing Leads Assigned To You | A: In Sprint Automation | Batman | HOJ     |

    @RetailRB_Fr
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay    | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                                                                         | NotificationCategory                                | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | FR  | RetailRB    | PBA      | Retail Advisor | Home | GIC_RESL    | Maturity         | Notifications    | Present | #Appels non effectués liés à de nouvelles pistes de CPG arrivant à échéance\n#Appels non effectués liés à de nouvelles opportunités CGBI arrivant à l'échéance | # Nouvelles Pistes Marketing Vous Ont été Attribuées | A: In Sprint Automation | Batman | HOJ     |

    @RetailRB_En
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | UserDisplay          | Page | MainFields | NotificationType    | NotificationName | State   | NotificationText                                                                  | NotificationCategory                       | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | EN  | RetailRB    | BM       | Retail Branch Manager | Home | GIC_RESL    | Maturity_Distribute | Notifications    | Present | # Unassigned GIC Maturity Leads to Distribute\n# Unassigned RESL Maturity Opportunities to Distribute | # Unassigned marketing leads to distribute | A: In Sprint Automation | Batman | HOJ     |
