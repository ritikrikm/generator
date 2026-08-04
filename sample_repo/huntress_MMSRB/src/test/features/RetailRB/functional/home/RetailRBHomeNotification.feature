Feature: Retail RB Home Notifications
  #Story: https://track.td.com/browse/CEPSCRMP-19127
  #Story: https://track.td.com/browse/CEPSCRMP-19129
  #Story: https://track.td.com/browse/CEPSCRMP-19130

  Scenario Outline: As "<SSOUser>" Home Page Notification for <Report> Verifying maturity notifications are linked
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" should be redirected to salesforce RB home page
    Then "User" clicks on "<Notification>" notification
    And "User" see "<Notification>" correctly linked to "<ListView>" listview

    @Bigbird-9998
    @RetailRB_En
    Examples:
      | SSOUser          | Report                             | Notification                                            | ListView                                      |
      | RETAIL_PBAUserId | MMSRB.Home.Reports.PBAReports      | MMSRB.Notification.NewUncalledGICMaturityLeads          | MMSRB.ListView.MyMaturityLeads               |
      | RETAIL_PBAUserId | MMSRB.Home.Reports.PBAReports      | MMSRB.Notification.NewUncalledRESLMaturityOpportunities | MMSRB.ListView.RetentionProgressRESL         |
      | RETAIL_BMUserId  | MMSRB.Home.Reports.BMReports       | MMSRB.Notification.UnassignedGICMaturityLeads           | MMSRB.ListView.UnassignedMaturityLeads       |
      | RETAIL_BMUserId  | MMSRB.Home.Reports.BMReports       | MMSRB.Notification.UnassignedRESLMaturityOpportunities  | MMSRB.ListView.RetentionProgressRESL         |

  Scenario Outline: As "<SSOUser>" Home Page Notification for <Report> Verifying maturity distribute notifications is NOT displayed
    Given "User" successfully logs in to RB with "<SSOUser>"
    When "User" should be redirected to salesforce RB home page
    Then "User" should able to see the "<Report>" notifications
    And "User" should NOT be able to see "<Notification>" notification

    @Bigbird-9998
    @RetailRB_En
    Examples:
      | SSOUser          | Report                             | Notification                                      |
      | RETAIL_BMUserId  | MMSRB.Home.Reports.BMReports       | MMSRB.Notification.UnassignedMaturityLeads        |
      | RETAIL_PBAUserId | MMSRB.Home.Reports.PBAReports      | MMSRB.Notification.NewMaturityLeadsAssignedToYou  |
