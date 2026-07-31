Feature: RetailRB Home Notification

  Scenario Outline: RetailRB home notifications are present for <Application> <Lan> <UserRole>
    Given Retail Advisor (<Lan>) user (Retail - <UserRole>) is logged into RB
    When the user navigates to the Home Page
    Then the HomePage should load successfully
    And notification section should be displayed
    And "<NotificationText>" notification should be displayed
    And both notification should appear under "<NotificationCategory>"

    @RetailRB_En
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                          | NotificationCategory                    | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | EN  | RetailRB    | PBA      | Home | GIC_RESL    | Maturity         | Notifications    | Present | # New, Uncalled GIC Maturity Leads\n# New, Uncalled RESL Maturity Opportunities | # New Marketing Leads Assigned To You | A: In Sprint Automation | Batman | HOJ     |

    @RetailRB_Fr
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                                                                           | NotificationCategory                    | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | FR  | RetailRB    | PBA      | Home | GIC_RESL    | Maturity         | Notifications    | Present | #Appels non effectués liés à de nouvelles pistes de CPG arrivant à échéance\n#Appels non effectués liés à de nouvelles opportunités RESL | # New Marketing Leads Assigned To You | A: In Sprint Automation | Batman | HOJ     |

    @RetailRB_En
    @BIGBIRD-4193
    Examples:
      | Labels       | Lan | Application | UserRole | Page | MainFields | NotificationType | NotificationName | State   | NotificationText                                                          | NotificationCategory                    | AutoAssessment          | POD    | MALCODE |
      | BIGBIRD-4193 | EN  | RetailRB    | BM       | Home | GIC_RESL    | Maturity         | Notifications    | Present | # New, Uncalled GIC Maturity Leads\n# New, Uncalled RESL Maturity Opportunities | # New Marketing Leads Assigned To You | A: In Sprint Automation | Batman | HOJ     |
