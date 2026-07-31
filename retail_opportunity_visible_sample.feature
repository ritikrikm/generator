Feature: Retail Opportunities Details Page Manage Components
  #Story: https://track.td.com/browse/CEPSCRMP-15783
  #Story: https://track.td.com/browse/CEPSCRMP-19372
  #Story: https://track.td.com/browse/CEPSCRMP-20427

  Scenario Outline: As "<SSOUser>" Manage Opportunity Details Sidebar components for "<Source>"
    Given "User" successfully logs in to RB with "<SSOUser>" for PCMR
    And "User" should be redirected to salesforce RB home page
    When "User" clicks on the Opportunities tab
    And "User" Selects the opportunities list view "<ListView>"
    And "User" Clicks on any opportunity name displayed on the list view "<Source>"
    Then "User" Should be redirected to Opportunity details page

    When "User" clicks on the "call" component
    Then "User" manages the "call" component
    And "User" edits the "call" component

    When "User" clicks on the "task" component
    Then "User" manages the "task" component

    When "User" clicks on the "notes" component
    Then "User" manages the "notes" component
    And "User" deletes the "notes" component

    When "User" clicks on the "upcoming" component
    Then "User" manages the "upcoming" component
    And "User" deletes the "upcoming" component

    @APR26_En
    @RetailRB_En
    @TCEPSCRMP-51266
    @TCEPSCRMP-51098
    Examples:
      | SSOUser          | ListView                            | Source        |
      | RETAIL_PBAUserId | RetailRB.ListView.MyOpportunities   | Opp.Marketing |

    @APR26_En
    @RetailRB_En
    @TCEPSCRMP-51268
    @TCEPSCRMP-51099
    Examples:
      | SSOUser         | ListView                            | Source        |
      | RETAIL_BMUserId | RetailRB.ListView.MyOpportunities   | Opp.Marketing |

    @APR26_Fr
    @RetailRB_Fr
    @TCEPSCRMP-51270
    @TCEPSCRMP-51102
    Examples:
      | SSOUser          | ListView                            | Source        |
      | RETAIL_PBAUserId | RetailRB.ListView.MyOpportunities   | Opp.Marketing |

    @APR26_Fr
    @RetailRB_Fr
    @TCEPSCRMP-51272
    @TCEPSCRMP-51102
    Examples:
      | SSOUser         | ListView                            | Source        |
      | RETAIL_BMUserId | RetailRB.ListView.MyOpportunities   | Opp.Marketing |

  Scenario Outline: Create Task as "<SSOUser>" for Marketing Opportunity not owned by him
    Given "User" successfully logs in to RB with "<SSOUser>"
    And "User" should be redirected to salesforce RB home page
    When "User" clicks on the Opportunities tab
    And "User" Selects the opportunities list view "<ListView>"
    And "User" clicks on any opportunity name displayed on the list view excluding lead source "MMSRB.Opp.Digital"
    And "<SSOUser>" changes the lead owner to "<ChangeOwner>" in Opp
    Then "User" Should be able to manage the "OpenActivities" component in opportunity detail page
    And "User" deletes the open activities
    And "User" Should be able to manage the "ActivityHistory" component in opportunity detail page
    And "User" deletes the open activities
    And "User" Should be able to manage the "notes" component in opportunity detail page
    And "<ChangeOwner>" changes the lead owner to "<SSOUser>" in Opp

    @JUL25_En
    @RetailRB_En
    @TCEPSCRMP-37154
    Examples:
      | SSOUser          | ListView                          | ChangeOwner     |
      | RETAIL_PBAUserId | RetailRB.ListView.MyOpportunities | MMSRB_FieldName |

    @JUL25_En
    @RetailRB_En
    @TCEPSCRMP-37155
    Examples:
      | SSOUser         | ListView                          | ChangeOwner       |
      | RETAIL_BMUserId | RetailRB.ListView.MyOpportunities | MMSRB_ManagerName |

    @JUL25_Fr
    @RetailRB_Fr
    @TCEPSCRMP-37161
    Examples:
      | SSOUser          | ListView                          | ChangeOwner     |
      | RETAIL_PBAUserId | RetailRB.ListView.MyOpportunities | MMSRB_FieldName |

    @JUL25_Fr
    @RetailRB_Fr
    @TCEPSCRMP-37162
    Examples:
      | SSOUser         | ListView                          | ChangeOwner       |
      | RETAIL_BMUserId | RetailRB.ListView.MyOpportunities | MMSRB_ManagerName |
