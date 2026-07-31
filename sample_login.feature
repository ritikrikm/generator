@regression @login_en
Feature: Login validation

  @smoke @web
  Scenario: Successful login with valid customer credentials
    Given user opens the login page
    When user enters username "ritik@example.com"
    And user enters password "ValidPass123"
    And user clicks the login button
    Then user should see the dashboard
    And user should see a welcome message

  @api @negative
  Scenario Outline: Login API rejects invalid credentials for <Lan>
    Given user prepares login API request
    When user sends username "<username>" and password "<password>"
    Then response status should be "<status>"
    And response message should be "<message>"

    Examples:
      | Lan | username           | password | status | message              |
      | EN  | wrong@example.com  | badpass  | 401    | Invalid credentials  |
      | FR  | faux@example.com   | badpass  | 401    | Identifiants invalides |
